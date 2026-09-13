from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualNoticeCreate(Strict):
    content: str = Field(min_length=1, max_length=5000)
    title: str | None = Field(default=None, max_length=200)
    published_at: str | None = None


class ManualNoticeOut(Strict):
    notice_id: str
    duplicate: bool
    source_code: str


class WorkflowActionOut(Strict):
    action_id: str
    action_type: str
    risk_level: str
    status: str
    task_id: str | None = None
    error_code: str | None = None


class NoticeWorkflowOut(Strict):
    workflow_id: str
    notice_id: str
    status: str
    source_code: str
    source_revision: int
    extracted_facts: dict
    uncertainty_codes: list[str]
    checklist: list[str]
    action_risk: str
    difference: dict
    automation_enabled: bool
    actions: list[WorkflowActionOut]
    created_at: str
    updated_at: str


class WorkflowConfirmation(Strict):
    approved: bool


class WorkflowExecute(Strict):
    idempotency_key: str = Field(min_length=1, max_length=128)


class SourceAutomationUpdate(Strict):
    enabled: bool


class SourceAutomationOut(Strict):
    source_code: str
    automation_enabled: bool
