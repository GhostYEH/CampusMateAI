from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from ..database.sqlite_db import Database
from ..models.model_capability import ModelCapabilityRequest, ModelCapabilityResult
from ..models.model_shadow import ModelShadowRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class ShadowIdempotencyConflict(ValueError):
    """The same request key was reused with a different sanitized input."""


class ModelShadowRepository:
    def __init__(self, db: Database, *, retention_days: int = 30) -> None:
        self._db = db
        self._retention_days = max(1, min(3650, retention_days))

    def record_result(self, *, request: ModelCapabilityRequest, result: ModelCapabilityResult,
                      production_model_key: str = "mature", dataset_version: str | None = None,
                      online_sample_version: str | None = "online-v1", evaluator_version: str = "shadow-evaluator-v1") -> ModelShadowRecord:
        created = _now()
        expires = (datetime.now(timezone.utc) + timedelta(days=self._retention_days)).isoformat()
        shadow_id = _id("shadow")
        with self._db.transaction() as conn:
            existing = conn.execute(
                """SELECT r.*, x.schema_valid, x.policy_valid, x.abstained, x.used_fallback,
                          x.failure_code, x.latency_ms, x.resource_metrics_json, x.evaluator_version
                   FROM model_shadow_runs r JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                   WHERE r.scope='ONLINE' AND r.user_id IS ? AND r.request_id=? AND r.capability_name=? AND r.capability_version=?""",
                (request.subject_user_id, request.request_id, request.capability_name, request.capability_version),
            ).fetchone()
            if existing:
                if existing["input_digest"] != result.input_digest:
                    raise ShadowIdempotencyConflict("shadow request input digest conflict")
                return self._record_from_row(existing)
            conn.execute(
                """INSERT INTO model_shadow_runs
                   (shadow_run_id,scope,user_id,request_id,capability_name,capability_version,
                    production_model_key,candidate_model_key,dataset_version,online_sample_version,
                    prompt_version,input_digest,expected_output_digest,candidate_output_digest,created_at,expires_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (shadow_id, "ONLINE", request.subject_user_id, request.request_id, request.capability_name,
                 request.capability_version, production_model_key, result.model_key, dataset_version,
                 online_sample_version, result.prompt_version, result.input_digest, None, result.output_digest,
                 created, expires),
            )
            conn.execute(
                """INSERT INTO model_shadow_results
                   (shadow_run_id,schema_valid,policy_valid,abstained,used_fallback,failure_code,latency_ms,resource_metrics_json,evaluator_version,created_at,inference_source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (shadow_id, int(result.schema_valid), int(result.policy_valid),
                 int(bool(result.output_payload and result.output_payload.get("abstained"))), int(result.used_fallback),
                 result.failure_code, result.latency_ms, json.dumps(result.resource_metrics, sort_keys=True),
                 evaluator_version, created, result.inference_source),
            )
            row = conn.execute(
                """SELECT r.*, x.schema_valid, x.policy_valid, x.abstained, x.used_fallback,
                          x.failure_code, x.latency_ms, x.resource_metrics_json, x.evaluator_version,
                          x.inference_source
                   FROM model_shadow_runs r JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                   WHERE r.shadow_run_id=?""", (shadow_id,)
            ).fetchone()
        return self._record_from_row(row)

    def _record_from_row(self, row) -> ModelShadowRecord:
        inference_source = row["inference_source"] if "inference_source" in row.keys() else None
        if inference_source not in ("REAL_MODEL", "FIXTURE", "DETERMINISTIC_FALLBACK"):
            inference_source = "REAL_MODEL" if not bool(row["used_fallback"]) else "DETERMINISTIC_FALLBACK"
        return ModelShadowRecord(
            shadow_run_id=row["shadow_run_id"], scope=row["scope"], user_id=row["user_id"], request_id=row["request_id"],
            capability_name=row["capability_name"], capability_version=row["capability_version"],
            production_model_key=row["production_model_key"], candidate_model_key=row["candidate_model_key"],
            dataset_version=row["dataset_version"], online_sample_version=row["online_sample_version"],
            prompt_version=row["prompt_version"], input_digest=row["input_digest"],
            expected_output_digest=row["expected_output_digest"], candidate_output_digest=row["candidate_output_digest"],
            schema_valid=bool(row["schema_valid"]), policy_valid=bool(row["policy_valid"]), abstained=bool(row["abstained"]),
            used_fallback=bool(row["used_fallback"]), failure_code=row["failure_code"], latency_ms=int(row["latency_ms"]),
            resource_metrics=json.loads(row["resource_metrics_json"] or "{}"), evaluator_version=row["evaluator_version"],
            created_at=row["created_at"], expires_at=row["expires_at"], inference_source=inference_source,
        )

    def list_for_user(self, *, user_id: str, capability_name: str | None = None, limit: int = 100) -> list[ModelShadowRecord]:
        limit = max(1, min(100, limit))
        where = ["r.scope='ONLINE'", "r.user_id=?"]
        params: list = [user_id]
        if capability_name:
            where.append("r.capability_name=?"); params.append(capability_name)
        with self._db.query() as conn:
            rows = conn.execute(
                f"""SELECT r.*, x.schema_valid, x.policy_valid, x.abstained, x.used_fallback,
                           x.failure_code, x.latency_ms, x.resource_metrics_json, x.evaluator_version,
                           x.inference_source
                    FROM model_shadow_runs r JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                    WHERE {' AND '.join(where)} ORDER BY r.created_at DESC,r.shadow_run_id DESC LIMIT ?""",
                params + [limit],
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def summarize_for_user(self, *, user_id: str) -> dict[str, int]:
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN x.used_fallback=1 THEN 1 ELSE 0 END) AS fallback_count,
                          SUM(CASE WHEN x.policy_valid=0 THEN 1 ELSE 0 END) AS policy_failure_count
                   FROM model_shadow_runs r JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                   WHERE r.scope='ONLINE' AND r.user_id=?""", (user_id,),
            ).fetchone()
        return {"total": int(row["total"] or 0), "fallback_count": int(row["fallback_count"] or 0),
                "policy_failure_count": int(row["policy_failure_count"] or 0)}

    def record_offline_metrics(self, *, capability_name: str, capability_version: str, dataset_version: str,
                               evaluator_version: str, metrics: dict) -> str:
        raw = json.dumps(metrics, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO model_shadow_metric_records
                   (metric_record_id,shadow_run_id,scope,capability_name,capability_version,dataset_version,evaluator_version,metrics_digest,metrics_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (_id("metric"), None, "OFFLINE", capability_name, capability_version, dataset_version,
                 evaluator_version, digest, raw, _now()),
            )
        return digest

    # ===== Public query methods for canary gate and model transparency =====

    def get_latest_promotion_decision(self, *, capability_name: str) -> dict | None:
        """Return the latest promotion decision for a capability, or None."""
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT * FROM model_promotion_decisions
                   WHERE capability_name=? ORDER BY created_at DESC LIMIT 1""",
                (capability_name,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def has_real_inference(self, *, user_id: str, capability_name: str | None = None) -> bool:
        """Check if any shadow run for this user used explicit REAL_MODEL inference."""
        where = ["r.scope='ONLINE'", "r.user_id=?", "x.inference_source='REAL_MODEL'"]
        params: list = [user_id]
        if capability_name:
            where.append("r.capability_name=?")
            params.append(capability_name)
        with self._db.query() as conn:
            row = conn.execute(
                f"""SELECT COUNT(*) AS n FROM model_shadow_runs r
                    JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                    WHERE {' AND '.join(where)}""",
                params,
            ).fetchone()
        return int(row["n"] or 0) > 0

    def get_last_real_inference_at(self, *, user_id: str, capability_name: str | None = None) -> str | None:
        """Return the timestamp of the most recent REAL_MODEL shadow run, or None."""
        where = ["r.scope='ONLINE'", "r.user_id=?", "x.inference_source='REAL_MODEL'"]
        params: list = [user_id]
        if capability_name:
            where.append("r.capability_name=?")
            params.append(capability_name)
        with self._db.query() as conn:
            row = conn.execute(
                f"""SELECT r.created_at FROM model_shadow_runs r
                    JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                    WHERE {' AND '.join(where)} ORDER BY r.created_at DESC LIMIT 1""",
                params,
            ).fetchone()
        return row["created_at"] if row else None

    def get_inference_sources(self, *, user_id: str, capability_name: str | None = None) -> set[str]:
        """Return explicit inference_source values observed for this user."""
        where = ["r.scope='ONLINE'", "r.user_id=?"]
        params: list = [user_id]
        if capability_name:
            where.append("r.capability_name=?")
            params.append(capability_name)
        with self._db.query() as conn:
            rows = conn.execute(
                f"""SELECT DISTINCT x.inference_source AS source FROM model_shadow_runs r
                    JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                    WHERE {' AND '.join(where)}""",
                params,
            ).fetchall()
        return {row["source"] for row in rows if row["source"]}

    def has_performance_measurement(self, *, capability_name: str) -> bool:
        """Performance is measured only when an offline metric record exists."""
        with self._db.query() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM model_shadow_metric_records
                   WHERE capability_name=?""",
                (capability_name,),
            ).fetchone()
        return int(row["n"] or 0) > 0

    def has_any_shadow_run(self, *, user_id: str, capability_name: str | None = None) -> bool:
        """Check if any shadow run exists for this user."""
        where = ["r.scope='ONLINE'", "r.user_id=?"]
        params: list = [user_id]
        if capability_name:
            where.append("r.capability_name=?")
            params.append(capability_name)
        with self._db.query() as conn:
            row = conn.execute(
                f"""SELECT COUNT(*) AS n FROM model_shadow_runs r
                    JOIN model_shadow_results x ON x.shadow_run_id=r.shadow_run_id
                    WHERE {' AND '.join(where)}""",
                params,
            ).fetchone()
        return int(row["n"] or 0) > 0


__all__ = ["ModelShadowRepository", "ShadowIdempotencyConflict"]
