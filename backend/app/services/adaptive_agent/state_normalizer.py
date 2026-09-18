"""Turn Student World Model projections into a small comparable state vector.

This boundary deliberately keeps provenance beside every scalar.  A missing,
stale, or incomparable source is omitted from the numeric vector instead of
being coerced to zero.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_QUALITY = {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}
_PRESSURE = {"LOW": 0.2, "MODERATE": 0.5, "HIGH": 0.8, "VERY_HIGH": 1.0}


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


class AdaptiveStateNormalizer:
    """Load baseline run ids and an as-of post-state, then normalize both."""

    DIMENSIONS = ("mastery", "error_rate", "completion_rate", "backlog", "stress_risk", "consistency", "goal_gap")

    def __init__(self, *, state_service, comparator=None):
        self.state_service = state_service
        self.comparator = comparator

    def compare(self, *, intervention, as_of: datetime, evaluation_id: str | None = None,
                strategy_code: str) -> dict[str, Any]:
        baseline = {
            "CORE": intervention.baseline_core_run_id,
            "ACADEMIC": intervention.baseline_academic_run_id,
            "WORLD": intervention.baseline_world_run_id,
        }
        before_snapshots = self._load_baseline(intervention.user_id, baseline)
        after = self._project_after(intervention.user_id, as_of, evaluation_id)
        before_values, before_meta = self._vector(before_snapshots)
        after_values, after_meta = self._vector(after)
        records = {}
        for name in self.DIMENSIONS:
            b, a = before_meta.get(name), after_meta.get(name)
            if b and a:
                records[name] = {"before": b["value"], "after": a["value"],
                                 "before_run_id": b["run_id"], "after_run_id": a["run_id"],
                                 "before_snapshot_id": b["snapshot_id"], "after_snapshot_id": a["snapshot_id"],
                                 "before_observed_at": b["observed_at"], "after_observed_at": a["observed_at"],
                                 "before_valid_until": b["valid_until"], "after_valid_until": a["valid_until"],
                                 "before_data_quality": b["data_quality"], "after_data_quality": a["data_quality"],
                                 "before_confidence": b["confidence"], "after_confidence": a["confidence"],
                                 "evidence_refs": [ref for ref in (b["snapshot_id"], a["snapshot_id"]) if ref]}
        before_values["_dimensions"] = records
        after_values["_dimensions"] = records
        from .state_outcome_comparator import StateOutcomeComparator
        result = (self.comparator or StateOutcomeComparator()).compare(
            before=before_values, after=after_values, strategy_code=strategy_code,
            comparison_as_of=as_of.astimezone(timezone.utc).isoformat(),
            evidence_refs=sorted({ref for item in records.values() for ref in item["evidence_refs"]}),
        )
        result["dimensions"] = records
        result["learning_plan_feedback"] = self._feedback(intervention.user_id, intervention.plan_id)
        result["before_run_ids"] = {k: v for k, v in baseline.items() if v}
        result["after_run_ids"] = {k: v for k, v in after.get("run_ids", {}).items() if v}
        return result

    @staticmethod
    def _fresh(metadata: dict[str, Any], as_of: datetime) -> bool:
        valid_until = _parse(metadata.get("valid_until"))
        return valid_until is None or valid_until >= as_of.astimezone(timezone.utc)

    def _feedback(self, user_id: str, plan_id: str | None) -> list[dict[str, Any]]:
        db = getattr(getattr(self.state_service, "repository", None), "_db", None)
        if db is None or not plan_id:
            return []
        try:
            with db.query() as conn:
                rows = conn.execute(
                    "SELECT feedback_id,feedback,created_at FROM learning_plan_feedback WHERE user_id=? AND plan_id=? ORDER BY created_at,feedback_id",
                    (user_id, plan_id),
                ).fetchall()
            return [{"feedback_id": row["feedback_id"], "feedback": row["feedback"], "created_at": row["created_at"],
                     "role": "AUXILIARY_EVIDENCE"} for row in rows]
        except Exception:
            return []

    def _load_baseline(self, user_id: str, run_ids: dict[str, str | None]) -> list[Any]:
        out = []
        repository = getattr(self.state_service, "repository", None)
        for kind, run_id in run_ids.items():
            if not run_id or repository is None:
                continue
            getter = getattr(repository, "list_snapshots_for_run", None)
            if getter:
                out.extend(getter(user_id=user_id, run_id=run_id, projection_kind=kind))
        return out

    def _project_after(self, user_id: str, as_of: datetime, evaluation_id: str | None) -> dict[str, Any]:
        snapshots: list[Any] = []
        run_ids: dict[str, str] = {}
        for kind, method in (("CORE", "project_user"), ("ACADEMIC", "project_academic"), ("WORLD", "project_world")):
            fn = getattr(self.state_service, method, None)
            if fn is None:
                continue
            try:
                projected = fn(user_id, as_of=as_of, trigger="adaptive_outcome", exclude_evaluation_id=evaluation_id)
            except TypeError:
                projected = fn(user_id, as_of=as_of, trigger="adaptive_outcome")
            if projected:
                run_ids[kind] = projected.run_id
                snapshots.extend(projected.snapshots)
        return {"snapshots": snapshots, "run_ids": run_ids}

    def _vector(self, source: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        snapshots = source.get("snapshots", []) if isinstance(source, dict) else source
        values: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        for snapshot in snapshots or []:
            value = getattr(snapshot, "value", None) or {}
            quality = getattr(snapshot, "data_quality", "unavailable")
            confidence = float(getattr(snapshot, "confidence", _QUALITY.get(quality, 0.0)) or 0.0)
            common = {"run_id": getattr(snapshot, "run_id", None), "snapshot_id": getattr(snapshot, "snapshot_id", None),
                      "observed_at": getattr(snapshot, "observed_through", None) or getattr(snapshot, "computed_at", None),
                      "valid_until": getattr(snapshot, "valid_until", None),
                      "data_quality": quality, "confidence": confidence}
            candidates = {
                "mastery": value.get("own_mastery_rate", value.get("mastery")),
                "error_rate": value.get("error_rate"),
                "completion_rate": value.get("consistency_ratio", value.get("completion_rate")),
                "backlog": value.get("pending_task_count", value.get("backlog")),
                "stress_risk": value.get("stress_risk", _PRESSURE.get(value.get("pressure_band"))),
                "consistency": value.get("consistency_ratio", value.get("consistency")),
                "goal_gap": value.get("goal_gap"),
            }
            if candidates["mastery"] is not None and float(candidates["mastery"]) > 1:
                candidates["mastery"] = float(candidates["mastery"]) / 100.0
            if candidates["mastery"] is not None and candidates["error_rate"] is None:
                candidates["error_rate"] = 1.0 - float(candidates["mastery"])
            if candidates["goal_gap"] is None and value.get("average_progress_percent") is not None:
                candidates["goal_gap"] = 1.0 - float(value["average_progress_percent"]) / 100.0
            for name, candidate in candidates.items():
                if isinstance(candidate, (int, float)) and name not in metadata:
                    values[name] = float(candidate)
                    metadata[name] = {**common, "value": float(candidate)}
        return values, metadata


__all__ = ["AdaptiveStateNormalizer"]
