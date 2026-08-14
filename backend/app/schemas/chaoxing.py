from pydantic import BaseModel, Field

class ChaoxingLoginRequest(BaseModel):
    username: str
    password: str

class ChaoxingSyncStatus(BaseModel):
    status: str
    last_synced_at: str | None = None
    source: str | None = None
    courses: int = 0
    teachers: int = 0
    pending_assignments: int = 0
    notices: int = 0
    warnings: list[str] = Field(default_factory=list)
