"""Explicit, versioned learner choices; defaults are not observed preferences."""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LearnerPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    daily_capacity_minutes: int = Field(default=240, ge=15, le=720)
    quiet_hours_start: str | None = Field(
        default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$"
    )
    quiet_hours_end: str | None = Field(
        default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$"
    )
    semester_start_dates: dict[str, date] = Field(default_factory=dict, max_length=20)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("semester_start_dates")
    @classmethod
    def valid_semesters(cls, value: dict[str, date]) -> dict[str, date]:
        for semester, start in value.items():
            if not semester.strip() or len(semester) > 128:
                raise ValueError("semester must contain 1..128 characters")
            if start.weekday() != 0:
                raise ValueError("semester start must be the Monday of teaching week 1")
        return value

    @model_validator(mode="after")
    def quiet_hours_pair(self):
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("quiet hours must provide both start and end")
        if (
            self.quiet_hours_start is not None
            and self.quiet_hours_start == self.quiet_hours_end
        ):
            raise ValueError("quiet hours start and end must differ")
        return self


class LearnerPreferencesUpdate(LearnerPreferences):
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)


class LearnerPreferencesOut(LearnerPreferences):
    configured: bool = False
    version: int = Field(default=0, ge=0)
    updated_at: datetime | None = None
