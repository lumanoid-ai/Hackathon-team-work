"""H1 — job description likhna. Rigid template = professional document, na ke AI slop."""
from app.core.llm import llm_text
from app.database import db_session
from app.models import Job, Workspace
from app.tools.artifacts import save_artifact

JD_TEMPLATE_RULES = """Write a job description with EXACTLY these sections:

# {role}
**Location: {location}** · **Type: {employment_type}** · **Reports to: {reports_to}**

## About us
(2 sentences, from the company context)

## What you'll do
(5 bullets, each starting with a verb)

## What we're looking for
(must-have vs nice-to-have, split into two sub-lists)

## What we offer
(3 bullets)

Rules:
- No buzzwords like "rockstar", "ninja", "guru", "wear many hats".
- No salary unless it is given to you.
- Write for a real human reading this on their phone.
- Seniority: {seniority}. Must-have skills: {must_have}. Nice-to-have: {nice_to_have}.
- Markdown only, no preamble.

Company context:
{company_context}
{extra}
"""


def write_jd(role: str, seniority: str = "mid", must_have_skills: list[str] | None = None,
             nice_to_have_skills: list[str] | None = None, location: str = "Remote",
             employment_type: str = "Full-time", reports_to: str = "Engineering Manager",
             company_context: str = "", job_id: str | None = None,
             extra_context: str = "", task_id: str | None = None) -> dict:
    must_have_skills = must_have_skills or []
    nice_to_have_skills = nice_to_have_skills or []

    prompt = JD_TEMPLATE_RULES.format(
        role=role, location=location, employment_type=employment_type,
        reports_to=reports_to, seniority=seniority,
        must_have=", ".join(must_have_skills) or "infer from the role",
        nice_to_have=", ".join(nice_to_have_skills) or "infer from the role",
        company_context=company_context or "A growing technology company.",
        extra=f"\nAdditional data to weave in naturally:\n{extra_context}" if extra_context else "",
    )
    jd = llm_text(prompt, temperature=0.5)

    art_id = save_artifact("HR", "jd", f"JD — {role}", jd, task_id,
                           meta={"job_id": job_id, "seniority": seniority})

    if job_id:                                   # JD ko job row pe bhi chipka do
        db = db_session()
        try:
            job = db.get(Job, job_id)
            if job:
                job.jd_markdown = jd
                job.status = "open"
                db.commit()
        finally:
            db.close()

    return {"artifact_id": art_id, "type": "jd", "title": f"JD — {role}", "content": jd}


def get_company_context(workspace_id: str | None) -> str:
    if not workspace_id:
        return ""
    db = db_session()
    try:
        ws = db.get(Workspace, workspace_id)
        return ws.context if ws else ""
    finally:
        db.close()
