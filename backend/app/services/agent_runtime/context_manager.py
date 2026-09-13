from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from ...core.exceptions import AppException


@dataclass(frozen=True)
class ContextSnapshot:
    snapshot_id: str
    user_id: str
    scope: Mapping[str, Any]
    facts: Mapping[str, Any]
    source_refs: tuple[str, ...]
    source_digest: str
    generated_at: datetime
    valid_until: datetime
    truncated_sources: tuple[str, ...]


class ContextManager:
    def __init__(self, *, max_rows: int = 200, max_chars: int = 100_000, ttl_minutes: int = 15) -> None:
        self.max_rows, self.max_chars, self.ttl_minutes = max_rows, max_chars, ttl_minutes

    def build(self, *, user_id: str, scope: dict[str, Any], facts: dict[str, Any],
              source_refs: list[str], now: datetime) -> ContextSnapshot:
        bounded: dict[str, Any] = {}
        truncated: list[str] = []
        remaining = self.max_chars
        for key, value in facts.items():
            selected = value[:self.max_rows] if isinstance(value, list) else value
            if isinstance(value, list) and len(value) > self.max_rows:
                truncated.append(key)
            encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, default=str)
            if len(encoded) > remaining:
                selected = [] if isinstance(selected, list) else None
                truncated.append(key)
                encoded = json.dumps(selected)
            bounded[key] = selected
            remaining -= len(encoded)
        canonical = json.dumps({"scope": scope, "facts": bounded, "sources": source_refs}, sort_keys=True, default=str)
        return ContextSnapshot(
            snapshot_id=f"ctx_{uuid4().hex}", user_id=user_id,
            scope=MappingProxyType(dict(scope)), facts=MappingProxyType(bounded),
            source_refs=tuple(source_refs), source_digest=hashlib.sha256(canonical.encode()).hexdigest(),
            generated_at=now, valid_until=now + timedelta(minutes=self.ttl_minutes),
            truncated_sources=tuple(dict.fromkeys(truncated)),
        )

    @staticmethod
    def require_fresh(snapshot: ContextSnapshot, now: datetime) -> None:
        if now >= snapshot.valid_until:
            raise AppException(code="AGENT_CONTEXT_EXPIRED", http_status=409, message="运行上下文已过期")
