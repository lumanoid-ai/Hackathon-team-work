"""Poora database schema. Har table ka maqsad comment mein likha hai."""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, Integer, Text, Boolean, DateTime, Date, ForeignKey, JSON, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class Workspace(Base):
    """Ek company = ek workspace. Company context yahin se agent ko milta hai."""
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200))
    context: Mapped[str] = mapped_column(Text, default="")   # about us, culture, benefits
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Job(Base):
    """Internal job jo admin create karta hai (ya external se import hoti hai)."""
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"))
    title: Mapped[str] = mapped_column(String(200))
    seniority: Mapped[str] = mapped_column(String(50), default="mid")
    location: Mapped[str] = mapped_column(String(150), default="Remote")
    employment_type: Mapped[str] = mapped_column(String(50), default="Full-time")
    must_have_skills: Mapped[list] = mapped_column(JSON, default=list)
    nice_to_have_skills: Mapped[list] = mapped_column(JSON, default=list)
    jd_markdown: Mapped[str] = mapped_column(Text, default="")      # write_jd ka output
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|open|closed
    source: Mapped[str] = mapped_column(String(50), default="internal")  # internal|remotive|arbeitnow...
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    applications = relationship("Application", back_populates="job")


class Candidate(Base):
    """Insaan. Ek candidate kai jobs pe apply kar sakta hai (email = unique key)."""
    __tablename__ = "candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resume_path: Mapped[str] = mapped_column(Text, default="")
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)   # parse_resume ka output
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Application(Base):
    """Pipeline ka dil. Har state change pe email jata hai."""
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))

    # received -> screening -> shortlisted | on_hold | rejected
    #          -> interview_scheduled -> interviewed -> hired | rejected
    status: Mapped[str] = mapped_column(String(40), default="received", index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)  # advance|hold|pass
    reasoning: Mapped[dict] = mapped_column(JSON, default=dict)  # strengths/gaps/one_liner
    cover_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate")


class InterviewSlot(Base):
    """Admin apni availability yahan daalta hai. Agent inhi mein se slot uthata hai."""
    __tablename__ = "interview_slots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True)
    interviewer_email: Mapped[str] = mapped_column(String(200))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"))
    slot_id: Mapped[str] = mapped_column(String(36), ForeignKey("interview_slots.id"))
    meeting_link: Mapped[str] = mapped_column(Text, default="")
    ics_path: Mapped[str] = mapped_column(Text, default="")
    questions: Mapped[list] = mapped_column(JSON, default=list)  # screening questions
    status: Mapped[str] = mapped_column(String(30), default="scheduled")  # scheduled|done|no_show
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Artifact(Base):
    """Agent jo bhi document banata hai (JD, checklist, questions) wo yahan save hota hai."""
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agent: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50))   # jd|checklist|questions|scorecard|brief
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)      # markdown
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Task(Base):
    """Manager ko diya gaya ek kaam. Activity feed isi ke sath chalti hai."""
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    instruction: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="running")  # running|done|failed
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Event(Base):
    """Har tool_call / thinking / artifact / done event. UI baad mein isay stream karegi."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    agent: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(40))   # thinking|tool_call|artifact|handoff|done|error
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EmailLog(Base):
    """Har bheja gaya email. Debugging aur 'kya bheja tha' proof ke liye."""
    __tablename__ = "email_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    to_email: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    template: Mapped[str] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="sent")  # sent|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PolicyDoc(Base):
    """Uploaded handbook. Chunks ChromaDB mein jate hain, metadata yahan."""
    __tablename__ = "policy_docs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    filename: Mapped[str] = mapped_column(String(300))
    path: Mapped[str] = mapped_column(Text)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class HiringMetric(Base):
    """Data Analyst agent ke liye. Har status change ka time yahan record hota hai."""
    __tablename__ = "hiring_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36))
    application_id: Mapped[str] = mapped_column(String(36))
    from_status: Mapped[str] = mapped_column(String(40), default="")
    to_status: Mapped[str] = mapped_column(String(40))
    hours_in_previous: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
