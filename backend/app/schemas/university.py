from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UniversityOut(BaseModel):
    id: str
    name: str
    short_name: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    country: str
    level: Optional[str] = None
    logo_url: Optional[str] = None
    official_domain: Optional[str] = None
    official_website: Optional[str] = None
    academic_system_type: str
    academic_system_url: Optional[str] = None
    academic_provider: str
    forum_enabled: bool
    status: str
    is_demo: bool
    created_at: str
    updated_at: str


class UniversityPage(BaseModel):
    items: list[UniversityOut]
    page: int
    page_size: int
    total: int


class ProfileUniversityUpdate(BaseModel):
    university_id: Optional[str] = Field(..., min_length=1, max_length=128)


class ProfileUniversityOut(BaseModel):
    university_id: Optional[str] = None
    university: Optional[UniversityOut] = None


__all__ = ["ProfileUniversityOut", "ProfileUniversityUpdate", "UniversityOut", "UniversityPage"]
