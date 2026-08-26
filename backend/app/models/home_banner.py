from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HomeBannerRow:
    id: str
    eyebrow: str
    title: str
    subtitle: str
    cta_label: str
    image_url: str
    action_key: str
    theme_key: str
    sort_order: int
    status: str
    starts_at: Optional[str]
    ends_at: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "HomeBannerRow":
        return cls(**{field: row[field] for field in cls.__dataclass_fields__})


__all__ = ["HomeBannerRow"]
