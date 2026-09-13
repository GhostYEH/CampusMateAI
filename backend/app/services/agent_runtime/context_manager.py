"""ContextManager —— 不可变有界 ContextSnapshot(§5.1)。

从服务端数据构建快照,每源校验当前用户访问权限。
日志只记录 snapshot_id / source_digest,不记录原始敏感内容。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ...repositories.agent_runtime_repository import AgentRuntimeRepository
from .context_budget import DEFAULT_BUDGET_TOKENS, compact_facts


@dataclass
class ContextSnapshot:
    """不可变上下文快照。"""

    snapshot_id: str
    user_id: str
    scope: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
    source_digest: str = ""
    generated_at: str = ""
    valid_until: str = ""
    expired: bool = False
    budget_report: dict = field(default_factory=dict)


class ContextManager:
    """上下文管理器。"""

    def __init__(
        self,
        repository: AgentRuntimeRepository,
        *,
        ttl_minutes: int = 15,
        max_facts_bytes: int = 65536,
        budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    ) -> None:
        self._repo = repository
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_facts_bytes = max_facts_bytes
        self._budget_tokens = budget_tokens

    def build(
        self,
        *,
        user_id: str,
        run_id: Optional[str] = None,
        scope: Optional[dict] = None,
        facts: Optional[dict] = None,
        source_refs: Optional[list[str]] = None,
    ) -> ContextSnapshot:
        """构建并持久化快照。校验大小与用户隔离。"""
        scope = scope or {"user_id": user_id}
        facts = facts or {}
        source_refs = source_refs or []
        # 预算裁剪:超预算时按占用从大到小压缩,报告写回 facts 以便审计。
        facts, budget_report = compact_facts(facts, budget_tokens=self._budget_tokens)
        if budget_report.get("truncated"):
            facts = {**facts, "_context_budget": budget_report}
        # 大小限制
        facts_json = json.dumps(facts, ensure_ascii=False, sort_keys=True)
        if len(facts_json.encode("utf-8")) > self._max_facts_bytes:
            raise ValueError("facts 超过大小限制")
        # source_digest
        digest_input = json.dumps(
            {"scope": scope, "facts": facts, "source_refs": sorted(source_refs)},
            ensure_ascii=False,
            sort_keys=True,
        )
        source_digest = "sha256:" + hashlib.sha256(
            digest_input.encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc)
        valid_until = (now + self._ttl).isoformat()
        snapshot_id = self._repo.save_snapshot(
            user_id=user_id,
            run_id=run_id,
            source_digest=source_digest,
            valid_until=valid_until,
            scope=scope,
            facts=facts,
            source_refs=source_refs,
        )
        return ContextSnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            scope=scope,
            facts=facts,
            source_refs=source_refs,
            source_digest=source_digest,
            generated_at=now.isoformat(),
            valid_until=valid_until,
            budget_report=budget_report,
        )

    def load(self, snapshot_id: str, user_id: str) -> Optional[ContextSnapshot]:
        """加载快照并校验所有权 + 过期。"""
        row = self._repo.get_snapshot(snapshot_id)
        if not row:
            return None
        if row["user_id"] != user_id:
            return None
        now = datetime.now(timezone.utc)
        valid_until = datetime.fromisoformat(row["valid_until"])
        expired = now > valid_until
        return ContextSnapshot(
            snapshot_id=row["snapshot_id"],
            user_id=row["user_id"],
            scope=json.loads(row["scope_json"]),
            facts=json.loads(row["facts_json"]),
            source_refs=json.loads(row["source_refs_json"]),
            source_digest=row["source_digest"],
            generated_at=row["generated_at"],
            valid_until=row["valid_until"],
            expired=expired,
        )

    def assert_not_expired(self, snapshot: ContextSnapshot) -> None:
        """写入前校验快照未过期。过期快照可只读,不可写入。"""
        if snapshot.expired:
            from ...core.exceptions import AgentContextExpired
            raise AgentContextExpired("上下文快照已过期,请重新构建")


__all__ = ["ContextManager", "ContextSnapshot"]