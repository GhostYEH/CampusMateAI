from pydantic import BaseModel, Field, SecretStr

class AcademicBindRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: SecretStr = Field(...)

