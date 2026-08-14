"""SchoolRegistry — 学校注册中心。

聚合 universities + edu_systems + edu_system_configs，
统一对外提供"学校基础信息 + 教务系统列表"的合并视图。
"""
from __future__ import annotations

from typing import Optional

from ...models.edu import (
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_UNSUPPORTED,
    EDU_SYSTEM_UNKNOWN,
    EduSystemConfigRow,
    EduSystemRow,
    SYSTEM_KEY_UNDERGRADUATE_MAIN,
    URL_NOT_DISCOVERED,
)
from ...models.university import UniversityRow
from ...repositories.edu_repository import EduRepository
from ...repositories.university_repository import UniversityRepository


class SchoolRegistry:
    """学校注册中心：聚合 universities + edu_systems。"""

    def __init__(
        self,
        university_repo: UniversityRepository,
        edu_repo: EduRepository,
    ) -> None:
        self._university_repo = university_repo
        self._edu_repo = edu_repo

    def get_university(self, university_id: str) -> Optional[UniversityRow]:
        return self._university_repo.get_by_id(university_id)

    # ===== edu_systems (1:N) =====

    def list_systems(self, university_id: str) -> list[EduSystemRow]:
        return self._edu_repo.list_systems_by_university(university_id)

    def get_system_by_id(self, system_id: str) -> Optional[EduSystemRow]:
        return self._edu_repo.get_system_by_id(system_id)

    def get_system_by_key(self, university_id: str, system_key: str) -> Optional[EduSystemRow]:
        return self._edu_repo.get_system_by_key(university_id, system_key)

    def ensure_default_system(self, university_id: str, school_code: Optional[str] = None) -> EduSystemRow:
        return self._edu_repo.ensure_default_system(university_id, school_code=school_code)

    def upsert_system(self, university_id: str, system_key: str, **kwargs) -> EduSystemRow:
        return self._edu_repo.upsert_system(university_id=university_id, system_key=system_key, **kwargs)

    # ===== edu_system_configs (旧表兼容) =====

    def get_config(self, university_id: str) -> Optional[EduSystemConfigRow]:
        return self._edu_repo.get_config_by_university(university_id)

    def ensure_config(self, university_id: str) -> EduSystemConfigRow:
        existing = self._edu_repo.get_config_by_university(university_id)
        if existing is not None:
            return existing
        return self._edu_repo.upsert_config(university_id)

    def upsert_config(self, university_id: str, **kwargs) -> EduSystemConfigRow:
        return self._edu_repo.upsert_config(university_id, **kwargs)

    def is_supported(self, university_id: str) -> bool:
        systems = self.list_systems(university_id)
        for sys_row in systems:
            if sys_row.provider not in (EDU_PROVIDER_UNKNOWN, EDU_PROVIDER_UNSUPPORTED):
                return True
        cfg = self.get_config(university_id)
        if cfg is not None and cfg.provider not in (EDU_PROVIDER_UNKNOWN, EDU_PROVIDER_UNSUPPORTED):
            return True
        return False


__all__ = ["SchoolRegistry"]
