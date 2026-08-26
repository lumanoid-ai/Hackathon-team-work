"""APScheduler — 3 background jobs. Yahi cheez system ko 'autonomous' banati hai."""
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.core.events import emit
from app.database import db_session
from app.models import Application, Candidate, Interview, InterviewSlot, Job, Workspace
from app.services.application_service import screen_pending
from app.services.email_service import send_template
from app.services.job_service import import_external_jobs

scheduler = BackgroundScheduler(timezone="UTC")


def job_screen_pending():
    res = screen_pending(limit=10)
    if res["processed"]:
        emit(None, "HR", "tool_call", f"{len(res['processed'])} applications auto-screen hui")


def job_sync_external():
    if not settings.JOB_SYNC_ENABLED:
        return
    db = db_session()
    try:
        ws = db.query(Workspace).first()
        ws_id = ws.id if ws else None
    finally:
        db.close()
    if not ws_id:
        return
    for q in settings.sync_queries:
        r = import_external_jobs(ws_id, q, limit=20)
        emit(None, "Manager", "tool_call",
             f"Job sync '{q}': {r['imported']} nayi jobs mili", r)


def job_interview_reminders():
    db = db_session()
    try:
        window = datetime.utcnow() + timedelta(hours=24)
        rows = (db.query(Interview, InterviewSlot, Application, Candidate, Job)
                .join(InterviewSlot, Interview.slot_id == InterviewSlot.id)
                .join(Application, Interview.application_id == Application.id)
                .join(Candidate, Application.candidate_id == Candidate.id)
                .join(Job, Application.job_id == Job.id)
                .filter(Interview.reminder_sent == False,          # noqa: E712
                        Interview.status == "scheduled",
                        InterviewSlot.start_at <= window,
                        InterviewSlot.start_at > datetime.utcnow()).all())
        for iv, slot, app_row, cand, job in rows:
            send_template(cand.email, "interview_reminder", {
                "candidate_name": cand.name or "there", "job_title": job.title,
                "when": slot.start_at.strftime("%d %b %Y, %H:%M UTC"),
                "meeting_link": iv.meeting_link})
            iv.reminder_sent = True
        db.commit()
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(job_screen_pending, "interval", minutes=2, id="screen", replace_existing=True)
    scheduler.add_job(job_sync_external, "interval", hours=6, id="jobsync", replace_existing=True)
    scheduler.add_job(job_interview_reminders, "interval", minutes=30, id="remind",
                      replace_existing=True)
    scheduler.start()
    print("[scheduler] chal para: screening 2min | job-sync 6h | reminders 30min")
