"""Agent Runtime 观测聚合 —— 只读、脱敏、有界。

设计约束(与 §2 不变量一致):
- **只读**:本模块不写任何表、不改任何运行状态,不提供重放或改状态的能力。
- **脱敏**:只输出计数、耗时、Token、状态与安全业务标识;
  绝不返回 prompt、完整模型内容、凭据、记忆正文或原始工具参数。
- **有界**:所有查询都带时间范围与最大行数限制,避免无界全表扫描。
- **聚合优先**:概览接口只返回聚合值,逐 Run 明细走单独的 trace 接口。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ...repositories.agent_runtime_repository import AgentRuntimeRepository

# 单次查询的硬上限。管理员接口不接受无界查询。
MAX_TRACE_EVENTS = 200
MAX_TRACE_TOOL_CALLS = 100
MAX_TRACE_MODEL_CALLS = 100

_TERMINAL = ("SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _percentile(values: list[float], ratio: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return round(ordered[index], 2)


def _duration_ms(start: Optional[str], end: Optional[str]) -> Optional[float]:
    if not start or not end:
        return None
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except (TypeError, ValueError):
        return None
    return max(0.0, delta.total_seconds() * 1000.0)


class AgentObservabilityService:
    """把仓储里的原始行折叠成安全的聚合视图。"""

    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repo = repository

    # ===== 概览 =====

    def overview(self, *, since_hours: int = 24) -> dict[str, Any]:
        since = (_now() - timedelta(hours=max(1, min(since_hours, 24 * 30)))).isoformat()
        now_iso = _now().isoformat()
        runs = self._repo.observability_runs(since=since)
        model_calls = self._repo.observability_model_calls(since=since)
        tool_calls = self._repo.observability_tool_calls(since=since)
        approvals = self._repo.observability_approvals(since=since)
        queue_depth = self._repo.count_runs_by_status("QUEUED")
        stale_leases = self._repo.count_stale_leases(now=now_iso)

        status_distribution: dict[str, int] = {}
        for run in runs:
            status = run.get("status") or "UNKNOWN"
            status_distribution[status] = status_distribution.get(status, 0) + 1

        terminal = [r for r in runs if r.get("status") in _TERMINAL]
        succeeded = [r for r in terminal if r.get("status") == "SUCCEEDED"]
        run_durations = [
            value
            for value in (
                _duration_ms(r.get("started_at"), r.get("finished_at")) for r in terminal
            )
            if value is not None
        ]
        model_latencies = [
            float(m["latency_ms"]) for m in model_calls if isinstance(m.get("latency_ms"), (int, float))
        ]
        total_tokens = sum(int(m.get("total_tokens") or 0) for m in model_calls)
        approval_waits = [
            value
            for value in (
                _duration_ms(a.get("created_at"), a.get("resolved_at")) for a in approvals
            )
            if value is not None
        ]

        return {
            "window_hours": since_hours,
            "since": since,
            "queue_depth": queue_depth,
            "stale_lease_count": stale_leases,
            "run_count": len(runs),
            "status_distribution": status_distribution,
            "success_rate": (
                round(len(succeeded) / len(terminal), 4) if terminal else None
            ),
            "duration_ms": {
                "p50": _percentile(run_durations, 0.5),
                "p95": _percentile(run_durations, 0.95),
                "samples": len(run_durations),
            },
            "model_latency_ms": {
                "p50": _percentile(model_latencies, 0.5),
                "p95": _percentile(model_latencies, 0.95),
                "samples": len(model_latencies),
            },
            "token_usage": {
                "total_tokens": total_tokens,
                "model_calls": len(model_calls),
            },
            "tool_failure_count": sum(
                1 for t in tool_calls if t.get("status") == "failed"
            ),
            "tool_call_count": len(tool_calls),
            "retry_count": sum(1 for r in runs if int(r.get("attempt_no") or 0) > 1),
            "approval": {
                "pending": sum(1 for a in approvals if a.get("status") == "PENDING"),
                "resolved": sum(1 for a in approvals if a.get("status") in {"APPROVED", "REJECTED"}),
                "expired": sum(1 for a in approvals if a.get("status") == "EXPIRED"),
                "wait_p50_ms": _percentile(approval_waits, 0.5),
                "wait_p95_ms": _percentile(approval_waits, 0.95),
            },
        }

    # ===== 单 Run 时间线 =====

    def run_trace(self, run_id: str) -> Optional[dict[str, Any]]:
        run = self._repo.get_run(run_id)
        if run is None:
            return None
        events = self._repo.list_events(run_id, after_sequence=0, limit=MAX_TRACE_EVENTS)
        tool_calls = self._repo.list_tool_calls_by_run(run_id, limit=MAX_TRACE_TOOL_CALLS)
        model_calls = self._repo.list_model_calls_by_run(run_id, limit=MAX_TRACE_MODEL_CALLS)
        approvals = self._repo.list_approvals_by_run(run_id)

        return {
            "run": {
                "run_id": run["run_id"],
                "job_id": run["job_id"],
                "status": run["status"],
                "phase": run["phase"],
                "risk_level": run.get("risk_level"),
                "handler_code": run.get("handler_code"),
                "handler_version": run.get("handler_version"),
                "attempt_no": int(run.get("attempt_no") or 0),
                "error_code": run.get("error_code"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "duration_ms": _duration_ms(run.get("started_at"), run.get("finished_at")),
            },
            "events": [
                {
                    "sequence": e["sequence"],
                    "type": e["type"],
                    "status": e["status"],
                    "phase": e["phase"],
                    "role": e.get("role"),
                    # summary 在写入时已是安全摘要;这里仍然只回显摘要字段本身。
                    "summary": e.get("summary"),
                    "created_at": e["created_at"],
                }
                for e in events
            ],
            "tool_calls": [
                {
                    "call_id": t["call_id"],
                    "tool_name": t["tool_name"],
                    "status": t["status"],
                    "error_code": t.get("error_code"),
                    "started_at": t["started_at"],
                    "finished_at": t.get("finished_at"),
                    "duration_ms": _duration_ms(t.get("started_at"), t.get("finished_at")),
                }
                for t in tool_calls
            ],
            "model_calls": [
                {
                    "call_id": m["call_id"],
                    "provider": m["provider"],
                    "model": m["model"],
                    "route_policy": m["route_policy"],
                    "status": m["status"],
                    "latency_ms": m.get("latency_ms"),
                    "total_tokens": m.get("total_tokens"),
                    "started_at": m["started_at"],
                }
                for m in model_calls
            ],
            "approvals": [
                {
                    "approval_id": a["approval_id"],
                    "status": a["status"],
                    "risk_level": a["risk_level"],
                    "action_summary": a["action_summary"],
                    "wait_ms": _duration_ms(a.get("created_at"), a.get("resolved_at")),
                    "expires_at": a["expires_at"],
                }
                for a in approvals
            ],
        }


__all__ = ["AgentObservabilityService", "MAX_TRACE_EVENTS"]
