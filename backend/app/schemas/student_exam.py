"""Request contract for manually recorded student exams."""

from pydantic import BaseModel, Field


class ExamIn(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=200)
    exam_date: str = Field(..., min_length=1, max_length=32)
    start_time: str | None = Field(None, max_length=16)
    end_time: str | None = Field(None, max_length=16)
    location: str | None = Field(None, max_length=200)
    seat_number: str | None = Field(None, max_length=32)
    exam_type: str | None = Field(None, max_length=64)
    reminder_enabled: bool = True
    notes: str | None = Field(None, max_length=2000)
