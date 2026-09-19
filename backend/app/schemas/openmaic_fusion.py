"""Schemas for the managed OpenMAIC fusion boundary."""

from pydantic import BaseModel, Field


class FusionStatus(BaseModel):
    enabled: bool
    available: bool
    capabilities: list[str] = Field(default_factory=list)
    reason: str


__all__ = ["FusionStatus"]
