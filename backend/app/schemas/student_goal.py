from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

GoalCategory = Literal[
    "academic",
    "research",
    "competition",
    "certificate",
    "job_search",
    "internship",
    "campus_affair",
    "health_habit",
    "personal_growth",
]
GoalStatus = Literal["active", "archived"]


class StudentGoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    category: GoalCategory
    target_date: Optional[str] = Field(None, max_length=32)
    idempotency_key: Optional[str] = Field(None, max_length=128)
    initial_progress_percent: float = Field(default=0.0, ge=0, le=100)
    milestone_count: int = Field(default=0, ge=0, le=100)


class StudentGoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[GoalCategory] = None
    target_date: Optional[str] = Field(None, max_length=32)
    milestone_count: Optional[int] = Field(None, ge=0, le=100)


class StudentGoalProgressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress_percent: float = Field(..., ge=0, le=100)
    milestone_reached: Optional[str] = Field(None, max_length=128)
    idempotency_key: Optional[str] = Field(None, max_length=128)


class StudentGoalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: str
    user_id: str
    name: str
    category: GoalCategory
    status: GoalStatus
    target_date: Optional[str] = None
    archived_at: Optional[str] = None
    progress_percent: float
    milestone_count: int
    created_at: str
    updated_at: str


class StudentGoalProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress_id: str
    goal_id: str
    progress_percent: float
    milestone_reached: Optional[str] = None
    occurred_at: str
    created_at: str


class StudentGoalCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: StudentGoalOut
    created: bool


class StudentGoalProgressResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: StudentGoalOut
    progress: StudentGoalProgressOut
    created: bool


class StudentGoalPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[StudentGoalOut]
    total: int
    page: int
    page_size: int
    has_more: bool


__all__ = [
    "GoalCategory",
    "GoalStatus",
    "StudentGoalCreate",
    "StudentGoalCreateResult",
    "StudentGoalOut",
    "StudentGoalPage",
    "StudentGoalProgressCreate",
    "StudentGoalProgressOut",
    "StudentGoalProgressResult",
    "StudentGoalUpdate",
]