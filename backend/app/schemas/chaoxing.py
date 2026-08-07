from pydantic import BaseModel

class ChaoxingLoginRequest(BaseModel):
    username: str
    password: str

class ChaoxingSyncStatus(BaseModel):
    status: str
    last_synced_at: str | None = None
