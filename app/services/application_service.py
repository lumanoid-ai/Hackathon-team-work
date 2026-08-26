"""PIPELINE — poore system ka dil.

apply -> received (email)
      -> screening (parse + score)
      -> shortlisted (email) -> interview auto-schedule (email + .ics)
      -> on_hold  (waiting email)
      -> rejected (rejection email)
      -> hired    (offer email + onboarding checklist email)

Har status change: DB update + email + event + metric row.
"""
from datetime import datetime

from app.config import settings
from app.core.events import emit
from app.database import db_session
from app.models import Application, Candidate, HiringMetric, Job
from app.services.email_service import send_template
from app.tools.resume_tools import parse_resume, score_candidate


# ---------------- helper ----------------
def _transition(db, app_row: Application, new_status: str) -> None:
    old = app_row.status
    hours = (datetime.utcnow() - app_row.updated_at).total_seconds() / 3600
    app_row.status = new_status
    db.add(HiringMetric(job_id=app_row.job_id, application_id=app_row.id,
                        from_status=old, to_status=new_status, hours_in_previous=hours))
    db.commit()


# ---------------- 1. apply ----------------
def create_application(job_id: str, email: str, name: str, resume_path: str,
                       phone: str = "", cover_note: str = "") -> dict:
    db = db_session()
    try:
        job = db.get(Job, job_id)
        if not job:
            return {"error": "job nahi mili"}

        cand = db.query(Candidate).filter(Candidate.email == email).first()
        if not cand:
            cand = Candidate(email=email, name=name, phone=phone, resume_path=resume_path)
            db.add(cand)
        else:
            cand.resume_path = resume_path or cand.resume_path
            cand.name = name or cand.name
        db.flush()

        dup = db.query(Application).filter(
            Application.job_id == job_id, Application.candidate_id == cand.id).first()
        if dup:
            return {"application_id": dup.id, "status": dup.status, "duplicate": True}

        app_row = Application(job_id=job_id, candidate_id=cand.id,
                              cover_note=cover_note, status="received")
        db.add(app_row)
        db.commit()
        db.refresh(app_row)

        send_template(email, "application_received", {
            "candidate_name": name or "there", "job_title": job.title,
            "application_id": app_row.id})
        emit(None, "HR", "tool_call", f"Nayi application: {email} -> {job.title}",
             {"application_id": app_row.id})
        return {"application_id": app_row.id, "status": "received"}
    finally:
        db.close()


# ---------------- 2. screen ----------------
def screen_application(application_id: str, task_id: str | None = None) -> dict:
    """Parse + score + decision + email. Background task ya scheduler isay chalata hai."""
    db = db_session()
    try:
        app_row = db.get(Application, application_id)
        if not app_row or app_row.status != "received":
            return {"skipped": True}
        job = db.get(Job, app_row.job_id)
        cand = db.get(Candidate, app_row.candidate_id)

        _transition(db, app_row, "screening")
        emit(task_id, "HR", "tool_call", f"Screening {cand.email}", {"application_id": app_row.id})

        parsed = cand.parsed or {}
        if not parsed and cand.resume_path:
            parsed = parse_resume(cand.resume_path)
            cand.parsed = parsed
            if parsed.get("name") and not cand.name:
                cand.name = parsed["name"]
            db.commit()

        jd = job.jd_markdown or f"{job.title} — must have: {', '.join(job.must_have_skills)}"
        result = score_candidate(parsed, jd)

        app_row.score = result["score"]
        app_row.verdict = result["verdict"]
        app_row.reasoning = {k: result.get(k) for k in ("strengths", "gaps", "one_liner")}
        db.commit()

        ctx = {"candidate_name": cand.name or "there", "job_title": job.title,
               "note": result.get("one_liner", "")}

        if result["score"] >= settings.SHORTLIST_THRESHOLD:
            _transition(db, app_row, "shortlisted")
            send_template(cand.email, "shortlisted", ctx)
            emit(task_id, "HR", "tool_call",
                 f"SHORTLIST {cand.email} ({result['score']})", {"score": result["score"]})
            if settings.AUTO_SCHEDULE_INTERVIEW:
                from app.tools.interview_tools import schedule_interview
                schedule_interview(app_row.id, task_id=task_id)

        elif result["score"] >= settings.HOLD_THRESHOLD:
            _transition(db, app_row, "on_hold")
            send_template(cand.email, "waiting", ctx)
            emit(task_id, "HR", "tool_call", f"HOLD {cand.email} ({result['score']})")

        else:
            _transition(db, app_row, "rejected")
            send_template(cand.email, "rejected", ctx)
            emit(task_id, "HR", "tool_call", f"REJECT {cand.email} ({result['score']})")

        return {"application_id": app_row.id, "score": result["score"],
                "status": app_row.status, "reasoning": app_row.reasoning}
    finally:
        db.close()


def screen_pending(limit: int = 20) -> dict:
    """Scheduler har 2 minute pe yeh chalata hai — plain Python loop, LLM decision nahi."""
    db = db_session()
    try:
        ids = [a.id for a in db.query(Application)
               .filter(Application.status == "received").limit(limit).all()]
    finally:
        db.close()
    return {"processed": [screen_application(i) for i in ids]}


# ---------------- 3. hire ----------------
def mark_interviewed(application_id: str, passed: bool, note: str = "") -> dict:
    db = db_session()
    try:
        app_row = db.get(Application, application_id)
        cand = db.get(Candidate, app_row.candidate_id)
        job = db.get(Job, app_row.job_id)
        _transition(db, app_row, "interviewed")
        if not passed:
            _transition(db, app_row, "rejected")
            send_template(cand.email, "rejected",
                          {"candidate_name": cand.name, "job_title": job.title, "note": note})
            return {"status": "rejected"}
        return {"status": "interviewed", "next": "make_offer()"}
    finally:
        db.close()


def make_offer(application_id: str, start_date: str, note: str = "") -> dict:
    """Offer + onboarding checklist — dono email, poora automated."""
    from app.tools.onboarding_tools import build_onboarding_checklist

    db = db_session()
    try:
        app_row = db.get(Application, application_id)
        cand = db.get(Candidate, app_row.candidate_id)
        job = db.get(Job, app_row.job_id)
        _transition(db, app_row, "hired")

        send_template(cand.email, "offer", {
            "candidate_name": cand.name or "there", "job_title": job.title,
            "start_date": start_date, "note": note})

        checklist = build_onboarding_checklist(job.title, start_date)
        html = "".join(
            f"<h3>{b.replace('_',' ').title()}</h3><ul>" +
            "".join(f"<li>{i['task']} <small>({i.get('owner','HR')})</small></li>"
                    for i in items) + "</ul>"
            for b, items in checklist["checklist"].items())
        send_template(cand.email, "onboarding", {
            "candidate_name": cand.name or "there", "start_date": start_date,
            "checklist_html": html})

        emit(None, "HR", "done", f"HIRED: {cand.email} for {job.title}",
             {"artifact": checklist["artifact_id"]})
        return {"status": "hired", "onboarding_artifact": checklist["artifact_id"]}
    finally:
        db.close()
