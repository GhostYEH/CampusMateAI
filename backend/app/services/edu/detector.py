"""SystemDetector — 教务系统探测器。

根据学校信息识别教务厂商与系统类型，但**不编造 URL**。

探测策略（按优先级）：
1. 若 edu_systems 中已显式记录 provider（非 unknown/unsupported），直接返回。
2. 若 edu_system_configs 中已显式记录 provider（非 unknown/unsupported），返回。
3. 若 universities.academic_provider 已显式标记（非 unsupported），作为低置信度线索返回。
4. 否则返回 detected=False, provider=unknown, confidence=0.0。

输出 Evidence 列表，标注 detectionSource（CONFIG / FINGERPRINT / MANUAL / UNKNOWN）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...models.edu import (
    DETECTION_CONFIG,
    DETECTION_UNKNOWN,
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_UNSUPPORTED,
    EDU_SYSTEM_UNKNOWN,
    KNOWN_PROVIDERS,
)
from ...models.university import UniversityRow
from .registry import SchoolRegistry


@dataclass
class DetectEvidence:
    source: str
    detail: str
    weight: float = 0.0


@dataclass
class DetectResult:
    university_id: str
    provider: str
    system_type: str
    detected: bool
    confidence: float
    evidence: list[DetectEvidence] = field(default_factory=list)
    detection_source: str = DETECTION_UNKNOWN
    reason: Optional[str] = None


class SystemDetector:
    """教务系统探测器。"""

    def __init__(self, registry: SchoolRegistry) -> None:
        self._registry = registry

    def detect(self, university_id: str) -> DetectResult:
        university = self._registry.get_university(university_id)
        if university is None:
            return DetectResult(
                university_id=university_id,
                provider=EDU_PROVIDER_UNKNOWN,
                system_type=EDU_SYSTEM_UNKNOWN,
                detected=False,
                confidence=0.0,
                evidence=[DetectEvidence(source=DETECTION_UNKNOWN, detail="university not found")],
                detection_source=DETECTION_UNKNOWN,
                reason="university not found",
            )

        # 1. edu_systems 中已显式记录
        systems = self._registry.list_systems(university_id)
        for sys_row in systems:
            if sys_row.provider not in (EDU_PROVIDER_UNKNOWN, EDU_PROVIDER_UNSUPPORTED):
                return DetectResult(
                    university_id=university_id,
                    provider=sys_row.provider,
                    system_type=sys_row.system_type,
                    detected=True,
                    confidence=0.92,
                    evidence=[DetectEvidence(
                        source=DETECTION_CONFIG,
                        detail=f"edu_systems[{sys_row.system_key}] provider={sys_row.provider}",
                        weight=0.92,
                    )],
                    detection_source=DETECTION_CONFIG,
                    reason=f"edu_systems explicit record (system_key={sys_row.system_key})",
                )

        # 2. edu_system_configs 中已显式记录（旧表兼容）
        cfg = self._registry.get_config(university_id)
        if cfg is not None and cfg.provider not in (
            EDU_PROVIDER_UNKNOWN,
            EDU_PROVIDER_UNSUPPORTED,
        ):
            return DetectResult(
                university_id=university_id,
                provider=cfg.provider,
                system_type=cfg.system_type,
                detected=True,
                confidence=0.90,
                evidence=[DetectEvidence(
                    source=DETECTION_CONFIG,
                    detail=f"edu_system_configs provider={cfg.provider}",
                    weight=0.90,
                )],
                detection_source=DETECTION_CONFIG,
                reason="edu_system_configs explicit record (legacy)",
            )

        # 3. universities.academic_provider 作为低置信度线索
        if university.academic_provider not in (
            EDU_PROVIDER_UNSUPPORTED,
            EDU_PROVIDER_UNKNOWN,
            "",
        ):
            return DetectResult(
                university_id=university_id,
                provider=university.academic_provider,
                system_type=university.academic_system_type
                if university.academic_system_type != "unsupported"
                else EDU_SYSTEM_UNKNOWN,
                detected=True,
                confidence=0.3,
                evidence=[DetectEvidence(
                    source=DETECTION_CONFIG,
                    detail=f"universities.academic_provider={university.academic_provider} (unverified legacy field)",
                    weight=0.3,
                )],
                detection_source=DETECTION_CONFIG,
                reason="universities.academic_provider legacy field, unverified",
            )

        # 4. 无法探测
        return DetectResult(
            university_id=university_id,
            provider=EDU_PROVIDER_UNKNOWN,
            system_type=EDU_SYSTEM_UNKNOWN,
            detected=False,
            confidence=0.0,
            evidence=[DetectEvidence(
                source=DETECTION_UNKNOWN,
                detail="no explicit provider record",
            )],
            detection_source=DETECTION_UNKNOWN,
            reason="no explicit provider record; URL must not be guessed",
        )


__all__ = ["DetectResult", "DetectEvidence", "SystemDetector"]
