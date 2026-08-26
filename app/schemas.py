"""Request/response shapes."""
from datetime import datetime
from pydantic import BaseModel, EmailStr


class WorkspaceIn(BaseModel):
    name: str
    context: str = ""


class JobIn(BaseModel):
    workspace_id: str
    title: str
    seniority: str = "mid"
    location: str = "Remote"
    employment_type: str = "Full-time"
    must_have: list[str] = []
    nice_to_have: list[str] = []
    generate_jd: bool = True


class SlotIn(BaseModel):
    interviewer_email: EmailStr
    start_at: datetime
    end_at: datetime
    job_id: str | None = None


class TaskIn(BaseModel):
    instruction: str
    workspace_id: str | None = None


class OfferIn(BaseModel):
    application_id: str
    start_date: str
    note: str = ""


class InterviewResultIn(BaseModel):
    application_id: str
    passed: bool
    note: str = ""


class PolicyQuestion(BaseModel):
    question: str


class ImportJobsIn(BaseModel):
    workspace_id: str
    query: str
    limit: int = 20
    providers: list[str] | None = None
