from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AcademicAuthResult:
    status: str
    external_student_id: str | None = None
    credential_ref: str | None = None


class AcademicProvider(ABC):
    key: str

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> AcademicAuthResult: ...

    @abstractmethod
    async def refresh_session(self, credential_ref: str) -> AcademicAuthResult: ...

    @abstractmethod
    async def fetch_profile(self, credential_ref: str) -> dict: ...

    @abstractmethod
    async def fetch_courses(self, credential_ref: str) -> list[dict]: ...

    @abstractmethod
    async def fetch_schedule(self, credential_ref: str) -> list[dict]: ...

    @abstractmethod
    async def fetch_grades(self, credential_ref: str) -> list[dict]: ...

    @abstractmethod
    async def fetch_exams(self, credential_ref: str) -> list[dict]: ...


class UnsupportedAcademicProvider(AcademicProvider):
    key = "unsupported"

    async def authenticate(self, username: str, password: str) -> AcademicAuthResult:
        return AcademicAuthResult(status="unsupported")

    async def refresh_session(self, credential_ref: str) -> AcademicAuthResult:
        return AcademicAuthResult(status="unsupported")

    async def fetch_profile(self, credential_ref: str) -> dict:
        return {}

    async def fetch_courses(self, credential_ref: str) -> list[dict]:
        return []

    async def fetch_schedule(self, credential_ref: str) -> list[dict]:
        return []

    async def fetch_grades(self, credential_ref: str) -> list[dict]:
        return []

    async def fetch_exams(self, credential_ref: str) -> list[dict]:
        return []


PROVIDERS: dict[str, AcademicProvider] = {"unsupported": UnsupportedAcademicProvider()}

