from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace

from app.database import sqlite_db


def test_concurrent_init_db_constructs_one_shared_instance(monkeypatch):
    entered = Event()
    release = Event()
    second_started = Event()
    duplicate_constructed = Event()
    count_lock = Lock()
    created = []

    def construct(path):
        assert path is None
        instance = object()
        with count_lock:
            created.append(instance)
            if len(created) > 1:
                duplicate_constructed.set()
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("database construction was not released")
        return instance

    monkeypatch.setattr(sqlite_db, "_db_instance", None)
    monkeypatch.setattr(sqlite_db, "Database", construct)
    settings = SimpleNamespace(database_path=None)

    def second_initializer():
        second_started.set()
        return sqlite_db.init_db(settings)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(sqlite_db.init_db, settings)
        try:
            assert entered.wait(timeout=2)
            second = pool.submit(second_initializer)
            assert second_started.wait(timeout=2)
            assert not duplicate_constructed.wait(timeout=0.1)
        finally:
            release.set()
        assert first.result(timeout=3) is second.result(timeout=3)
    assert len(created) == 1
