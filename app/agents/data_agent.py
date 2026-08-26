"""Agent 3 (minimal) — Data Analyst. HR isse numbers maangta hai."""
from datetime import datetime, timedelta

from sqlalchemy import func

from app.core.base_agent import BaseAgent, Tool
from app.database import db_session
from app.models import Application, HiringMetric, Job


def time_to_hire(days: int = 90) -> dict:
    db = db_session()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        rows = db.query(HiringMetric).filter(
            HiringMetric.to_status == "hired", HiringMetric.created_at >= since).all()
        if not rows:
            return {"hires": 0, "avg_days_to_hire": None,
                    "note": "Abhi is period mein koi hire nahi hua"}
        totals = []
        for r in rows:
            app_row = db.get(Application, r.application_id)
            if app_row:
                totals.append((r.created_at - app_row.created_at).total_seconds() / 86400)
        return {"hires": len(totals), "avg_days_to_hire": round(sum(totals) / len(totals), 1)}
    finally:
        db.close()


def funnel_stats(job_id: str | None = None) -> dict:
    db = db_session()
    try:
        q = db.query(Application.status, func.count(Application.id))
        if job_id:
            q = q.filter(Application.job_id == job_id)
        counts = dict(q.group_by(Application.status).all())
        total = sum(counts.values()) or 1
        return {"counts": counts,
                "shortlist_rate_pct": round(100 * counts.get("shortlisted", 0) / total, 1),
                "reject_rate_pct": round(100 * counts.get("rejected", 0) / total, 1)}
    finally:
        db.close()


def score_distribution(job_id: str | None = None) -> dict:
    db = db_session()
    try:
        q = db.query(Application.score).filter(Application.score.isnot(None))
        if job_id:
            q = q.filter(Application.job_id == job_id)
        scores = [s for (s,) in q.all()]
        if not scores:
            return {"n": 0}
        return {"n": len(scores), "avg": round(sum(scores) / len(scores), 1),
                "min": min(scores), "max": max(scores)}
    finally:
        db.close()


def open_jobs() -> list[dict]:
    db = db_session()
    try:
        return [{"id": j.id, "title": j.title, "source": j.source}
                for j in db.query(Job).filter(Job.status == "open").all()]
    finally:
        db.close()


DATA_SYSTEM_PROMPT = """You are the Data Analyst in an AI workforce.
You answer with numbers from the database only. Never estimate or invent a metric.
If the data is empty, say so plainly. Report in under 80 words."""

data_agent = BaseAgent(
    name="Data",
    role="Metrics, funnels, hiring analytics",
    system_prompt=DATA_SYSTEM_PROMPT,
    tools=[
        Tool("time_to_hire", time_to_hire, "Average days from application to hire", {"days": "int"}),
        Tool("funnel_stats", funnel_stats, "Counts per pipeline stage", {"job_id": "str"}),
        Tool("score_distribution", score_distribution, "Score spread", {"job_id": "str"}),
        Tool("open_jobs", open_jobs, "List currently open jobs", {}),
    ],
    color="#3B82F6",   # blue
)
