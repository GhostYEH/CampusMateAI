"""University tenancy rows kept independent from legacy multi-role models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UniversityRow:
    id: str
    name: str
    short_name: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    country: str = "China"
    level: Optional[str] = None
    school_code: Optional[str] = None
    logo_url: Optional[str] = None
    official_domain: Optional[str] = None
    official_website: Optional[str] = None
    academic_system_type: str = "unsupported"
    academic_system_url: Optional[str] = None
    academic_provider: str = "unsupported"
    forum_enabled: bool = False
    status: str = "active"
    is_demo: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "UniversityRow":
        return cls(
            id=row["id"],
            name=row["name"],
            short_name=row["short_name"],
            province=row["province"],
            city=row["city"],
            country=row["country"],
            level=row["level"],
            school_code=row["school_code"] if "school_code" in row.keys() else None,
            logo_url=row["logo_url"],
            official_domain=row["official_domain"],
            official_website=row["official_website"],
            academic_system_type=row["academic_system_type"],
            academic_system_url=row["academic_system_url"],
            academic_provider=row["academic_provider"],
            forum_enabled=bool(row["forum_enabled"]),
            status=row["status"],
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = ["UniversityRow"]
