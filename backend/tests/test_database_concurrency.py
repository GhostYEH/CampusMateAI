from __future__ import annotations

import threading
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from app.database.sqlite_db import Database


@pytest.mark.parametrize("failure_phase", ["execute", "commit"])
def test_dispose_closes_file_connection_when_checkpoint_fails(tmp_path, monkeypatch, failure_phase):
    database = Database(tmp_path / "failed-checkpoint.db")
    connection = Mock()
    getattr(connection, failure_phase).side_effect = sqlite3.OperationalError("checkpoint unavailable")
    monkeypatch.setattr(sqlite3, "connect", Mock(return_value=connection))
    database.dispose()
    connection.close.assert_called_once_with()


def _create_probe_table(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS concurrency_probe (value INTEGER NOT NULL)")
        conn.execute("DELETE FROM concurrency_probe")
        conn.execute("INSERT INTO concurrency_probe(value) VALUES (1)")


def test_file_queries_can_enter_concurrently(tmp_path):
    db = Database(tmp_path / "parallel-queries.db")
    barrier = threading.Barrier(2)
    try:
        def read_value():
            with db.query() as conn:
                value = conn.execute("SELECT 1").fetchone()[0]
                barrier.wait(timeout=3)
                return value

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(read_value)
            second = pool.submit(read_value)
            assert first.result(timeout=5) == 1
            assert second.result(timeout=5) == 1
    finally:
        db.dispose()


def test_file_reader_runs_during_uncommitted_writer_and_sees_committed_value(tmp_path):
    db = Database(tmp_path / "wal-reader-writer.db")
    _create_probe_table(db)
    writer_ready = threading.Event()
    release_writer = threading.Event()
    reader_done = threading.Event()
    observed: list[int] = []

    def write_uncommitted():
        with db.transaction() as conn:
            conn.execute("UPDATE concurrency_probe SET value=2")
            writer_ready.set()
            if not release_writer.wait(timeout=5):
                raise TimeoutError("writer release was not signaled")

    def read_committed():
        with db.query() as conn:
            observed.append(conn.execute("SELECT value FROM concurrency_probe").fetchone()[0])
        reader_done.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(write_uncommitted)
            assert writer_ready.wait(timeout=3)
            reader = pool.submit(read_committed)
            try:
                assert reader_done.wait(timeout=3), "WAL reader waited behind the writer"
                assert observed == [1]
            finally:
                release_writer.set()
            writer.result(timeout=5)
            reader.result(timeout=5)
        with db.query() as conn:
            assert conn.execute("SELECT value FROM concurrency_probe").fetchone()[0] == 2
    finally:
        release_writer.set()
        db.dispose()


def test_memory_query_and_transaction_share_connection_serially_and_rollback_baseexception():
    db = Database(None)
    _create_probe_table(db)
    query_entered = threading.Event()
    release_query = threading.Event()
    transaction_attempting = threading.Event()
    transaction_entered = threading.Event()

    def hold_query():
        with db.query():
            query_entered.set()
            if not release_query.wait(timeout=5):
                raise TimeoutError("query release was not signaled")

    def write_after_query():
        transaction_attempting.set()
        with db.transaction() as conn:
            transaction_entered.set()
            conn.execute("UPDATE concurrency_probe SET value=3")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            query = pool.submit(hold_query)
            assert query_entered.wait(timeout=3)
            writer = pool.submit(write_after_query)
            assert transaction_attempting.wait(timeout=3)
            try:
                assert not transaction_entered.wait(timeout=0.1)
            finally:
                release_query.set()
            query.result(timeout=3)
            writer.result(timeout=3)
        assert transaction_entered.is_set()

        class SimulatedCancellation(BaseException):
            pass

        with pytest.raises(SimulatedCancellation):
            with db.transaction() as conn:
                conn.execute("UPDATE concurrency_probe SET value=4")
                raise SimulatedCancellation()
        with db.query() as conn:
            assert conn.execute("SELECT value FROM concurrency_probe").fetchone()[0] == 3
    finally:
        release_query.set()
        db.dispose()


def test_file_transactions_remain_mutually_exclusive(tmp_path):
    db = Database(tmp_path / "serialized-writers.db")
    _create_probe_table(db)
    first_ready = threading.Event()
    release_first = threading.Event()
    second_attempting = threading.Event()
    second_entered = threading.Event()

    def first_writer():
        with db.transaction() as conn:
            conn.execute("UPDATE concurrency_probe SET value=2")
            first_ready.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("first writer release was not signaled")

    def second_writer():
        second_attempting.set()
        with db.transaction() as conn:
            second_entered.set()
            conn.execute("UPDATE concurrency_probe SET value=3")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_writer)
            assert first_ready.wait(timeout=3)
            second = pool.submit(second_writer)
            assert second_attempting.wait(timeout=3)
            try:
                assert not second_entered.wait(timeout=0.1)
            finally:
                release_first.set()
            first.result(timeout=5)
            second.result(timeout=5)
        with db.query() as conn:
            assert conn.execute("SELECT value FROM concurrency_probe").fetchone()[0] == 3
    finally:
        release_first.set()
        db.dispose()


def test_direct_memory_connection_borrows_isolate_commit_and_rollback():
    """Legacy repositories must not commit another thread's uncommitted work."""
    db = Database(None)
    _create_probe_table(db)
    first_ready = threading.Event()
    release_first = threading.Event()
    second_attempting = threading.Event()
    second_entered = threading.Event()

    def rolling_back_writer():
        conn = db._connect()
        try:
            conn.execute("UPDATE concurrency_probe SET value=2")
            first_ready.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("first borrower release was not signaled")
            conn.rollback()
        finally:
            db._release(conn)

    def committing_writer():
        second_attempting.set()
        conn = db._connect()
        try:
            second_entered.set()
            value = conn.execute("SELECT value FROM concurrency_probe").fetchone()[0]
            conn.execute("UPDATE concurrency_probe SET value=3")
            conn.commit()
            return value
        finally:
            db._release(conn)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(rolling_back_writer)
            assert first_ready.wait(timeout=3)
            second = pool.submit(committing_writer)
            assert second_attempting.wait(timeout=3)
            try:
                assert not second_entered.wait(timeout=0.1)
            finally:
                release_first.set()
            first.result(timeout=5)
            assert second.result(timeout=5) == 1
        with db.query() as conn:
            assert conn.execute("SELECT value FROM concurrency_probe").fetchone()[0] == 3
    finally:
        release_first.set()
        db.dispose()
