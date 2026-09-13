from pydantic import BaseModel,ConfigDict,Field
from .agent_contract_enums import AcademicPolicy,ResearchMode
from .agent_runtime import SourcePolicy

class Strict(BaseModel):model_config=ConfigDict(extra="forbid",use_enum_values=True)
class ResearchCreate(Strict):
    question:str=Field(min_length=2,max_length=4000)
    course_id:str|None=None
    mode:ResearchMode
    academic_policy:AcademicPolicy
    source_policy:SourcePolicy
class ResearchSourceOut(Strict):
    source_id:str;source_type:str;safe_label:str;verification_status:str
class ResearchOut(Strict):
    research_id:str;course_id:str|None;requested_mode:str;effective_mode:str;academic_policy:str
    source_policy:SourcePolicy;status:str;roles:list[str];warning_codes:list[str]
    report_summary:str;sources:list[ResearchSourceOut];created_at:str
