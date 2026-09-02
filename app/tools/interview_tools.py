# """H4 + H7 — screening questions aur interview scheduling (agent khud slot book karta hai)."""
# import os
# from datetime import datetime, timedelta

# from app.config import settings
# from app.core.events import emit
# from app.core.llm import llm_json
# from app.database import db_session
# from app.models import Application, Candidate, Interview, InterviewSlot, Job
# from app.tools.artifacts import save_artifact

# QUESTIONS_PROMPT = """Read this job description and write 5 role-specific screening questions.

# Return ONLY a JSON array:
# [{{"question": "...",
#    "why_ask": "what this reveals",
#    "good_answer_looks_like": "...",
#    "red_flag": "..."}}]

# No generic questions ("tell me about yourself"). Every question must be
# answerable only by someone who has actually done this job.

# JOB DESCRIPTION:
# {jd}
# """


# def generate_screening_questions(jd: str, job_id: str | None = None,
#                                  task_id: str | None = None) -> dict:
#     qs = llm_json(QUESTIONS_PROMPT.format(jd=jd[:4000]))
#     md = "\n\n".join(
#         f"### {i}. {q['question']}\n"
#         f"- **Why ask:** {q.get('why_ask','')}\n"
#         f"- **Good answer:** {q.get('good_answer_looks_like','')}\n"
#         f"- **Red flag:** {q.get('red_flag','')}"
#         for i, q in enumerate(qs, 1)
#     )
#     art_id = save_artifact("HR", "questions", "Screening questions", md, task_id,
#                            meta={"job_id": job_id, "questions": qs})
#     return {"artifact_id": art_id, "type": "questions", "title": "Screening questions",
#             "questions": qs, "content": md}


# # ---------------- scheduling ----------------
# def find_free_slot(job_id: str | None) -> InterviewSlot | None:
#     db = db_session()
#     try:
#         q = db.query(InterviewSlot).filter(
#             InterviewSlot.is_booked == False,                     # noqa: E712
#             InterviewSlot.start_at > datetime.utcnow() + timedelta(hours=12),
#         )
#         slot = (q.filter(InterviewSlot.job_id == job_id).order_by(InterviewSlot.start_at).first()
#                 or q.filter(InterviewSlot.job_id.is_(None)).order_by(InterviewSlot.start_at).first())
#         if slot:
#             db.expunge(slot)
#         return slot
#     finally:
#         db.close()


# def _write_ics(interview_id: str, title: str, start: datetime, end: datetime,
#                attendees: list[str], description: str) -> str:
#     """ICS file — koi paid calendar API ki zaroorat nahi, email attachment kaafi hai."""
#     os.makedirs(settings.ICS_DIR, exist_ok=True)
#     path = os.path.join(settings.ICS_DIR, f"{interview_id}.ics")
#     fmt = "%Y%m%dT%H%M%SZ"
#     lines = [
#         "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AI HR Agent//EN", "BEGIN:VEVENT",
#         f"UID:{interview_id}@hr-agent", f"DTSTAMP:{datetime.utcnow().strftime(fmt)}",
#         f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
#         f"SUMMARY:{title}", f"DESCRIPTION:{description}",
#         *[f"ATTENDEE;CN={a}:mailto:{a}" for a in attendees],
#         "END:VEVENT", "END:VCALENDAR",
#     ]
#     with open(path, "w", encoding="utf-8") as f:
#         f.write("\r\n".join(lines))
#     return path


# def schedule_interview(application_id: str, meeting_link: str = "",
#                        task_id: str | None = None) -> dict:
#     """Agent yeh tool tab chalata hai jab candidate shortlist ho jata hai."""
#     from app.services.email_service import send_template   # circular import se bachao

#     db = db_session()
#     try:
#         app_row = db.get(Application, application_id)
#         if not app_row:
#             return {"error": "application nahi mili"}
#         job = db.get(Job, app_row.job_id)
#         cand = db.get(Candidate, app_row.candidate_id)

#         slot = find_free_slot(job.id)
#         if not slot:
#             emit(task_id, "HR", "error", "Koi free interview slot nahi bacha")
#             return {"error": "no_slot", "message": "Admin ko slots add karne kehna"}

#         slot_row = db.get(InterviewSlot, slot.id)
#         slot_row.is_booked = True

#         questions = generate_screening_questions(job.jd_markdown or job.title, job.id, task_id)

#         interview = Interview(
#             application_id=application_id, slot_id=slot_row.id,
#             meeting_link=meeting_link or "Link email mein bheja jayega",
#             questions=questions["questions"],
#         )
#         db.add(interview)
#         db.commit()
#         db.refresh(interview)

#         interview.ics_path = _write_ics(
#             interview.id, f"Interview — {job.title} — {cand.name or cand.email}",
#             slot_row.start_at, slot_row.end_at,
#             [cand.email, slot_row.interviewer_email],
#             f"{job.title} interview at {settings.COMPANY_NAME}",
#         )
#         app_row.status = "interview_scheduled"
#         db.commit()

#         ctx = {
#             "candidate_name": cand.name or "there", "job_title": job.title,
#             "company": settings.COMPANY_NAME,
#             "when": slot_row.start_at.strftime("%d %b %Y, %H:%M UTC"),
#             "meeting_link": interview.meeting_link,
#             "interviewer": slot_row.interviewer_email,
#         }
#         send_template(cand.email, "interview_invite", ctx, attachment=interview.ics_path)
#         send_template(slot_row.interviewer_email, "interviewer_brief",
#                       {**ctx, "candidate_email": cand.email,
#                        "one_liner": (app_row.reasoning or {}).get("one_liner", ""),
#                        "questions": questions["questions"]})

#         emit(task_id, "HR", "tool_call",
#              f"Interview book ho gaya: {cand.email} @ {ctx['when']}",
#              {"interview_id": interview.id})
#         return {"interview_id": interview.id, "when": ctx["when"],
#                 "questions_artifact": questions["artifact_id"]}
#     finally:
#         db.close()










"""H4 + H7 — screening questions aur interview scheduling.

Scheduling do tarah se chalti hai:
  A) Interviewer ka Google Calendar juRa hai  -> asli event + Meet link, Google khud invite bhejta hai
  B) JuRa nahi hai                            -> .ics file banti hai aur hum email karte hain
Dono mein baaki flow bilkul same rehta hai.
"""
import os
from datetime import datetime, timedelta

from app.config import settings
from app.core.events import emit
from app.core.llm import llm_json
from app.database import db_session
from app.models import Application, Candidate, Interview, InterviewSlot, Job
from app.services import google_calendar as gcal
from app.tools.artifacts import save_artifact

QUESTIONS_PROMPT = """Read this job description and write 5 role-specific screening questions.

Return ONLY a JSON array:
[{{"question": "...",
   "why_ask": "what this reveals",
   "good_answer_looks_like": "...",
   "red_flag": "..."}}]

No generic questions ("tell me about yourself"). Every question must be
answerable only by someone who has actually done this job.

JOB DESCRIPTION:
{jd}
"""


def generate_screening_questions(jd: str, job_id: str | None = None,
                                 task_id: str | None = None) -> dict:
    qs = llm_json(QUESTIONS_PROMPT.format(jd=jd[:4000]))
    md = "\n\n".join(
        f"### {i}. {q['question']}\n"
        f"- **Why ask:** {q.get('why_ask','')}\n"
        f"- **Good answer:** {q.get('good_answer_looks_like','')}\n"
        f"- **Red flag:** {q.get('red_flag','')}"
        for i, q in enumerate(qs, 1)
    )
    art_id = save_artifact("HR", "questions", "Screening questions", md, task_id,
                           meta={"job_id": job_id, "questions": qs})
    return {"artifact_id": art_id, "type": "questions", "title": "Screening questions",
            "questions": qs, "content": md}


# ---------------- slot dhoondna ----------------
def find_free_slot(job_id: str | None) -> InterviewSlot | None:
    """Agla khali slot.

    DB mein slot khali dikh sakta hai lekin interviewer ke asli calendar par
    us waqt meeting ho — isliye connected calendar par free/busy bhi check karte hain.
    """
    db = db_session()
    try:
        q = db.query(InterviewSlot).filter(
            InterviewSlot.is_booked == False,                     # noqa: E712
            InterviewSlot.start_at > datetime.utcnow() + timedelta(hours=12),
        )
        candidates = (q.filter(InterviewSlot.job_id == job_id)
                        .order_by(InterviewSlot.start_at).all()
                      or q.filter(InterviewSlot.job_id.is_(None))
                        .order_by(InterviewSlot.start_at).all())

        for slot in candidates:
            if gcal.is_free(slot.interviewer_email, slot.start_at, slot.end_at):
                db.expunge(slot)
                return slot
            print(f"[calendar] {slot.start_at:%d %b %H:%M} par interviewer busy — agla slot")
        return None
    finally:
        db.close()


def _write_ics(interview_id: str, title: str, start: datetime, end: datetime,
               attendees: list[str], description: str) -> str:
    """Fallback: ICS file — koi paid calendar API ki zaroorat nahi."""
    os.makedirs(settings.ICS_DIR, exist_ok=True)
    path = os.path.join(settings.ICS_DIR, f"{interview_id}.ics")
    fmt = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AI HR Agent//EN", "BEGIN:VEVENT",
        f"UID:{interview_id}@hr-agent", f"DTSTAMP:{datetime.utcnow().strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{title}", f"DESCRIPTION:{description}",
        *[f"ATTENDEE;CN={a}:mailto:{a}" for a in attendees],
        "END:VEVENT", "END:VCALENDAR",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))
    return path


# ---------------- main tool ----------------
def schedule_interview(application_id: str, meeting_link: str = "",
                       task_id: str | None = None) -> dict:
    """Agent yeh tool tab chalata hai jab candidate shortlist ho jata hai."""
    from app.services.email_service import send_template   # circular import se bachao

    db = db_session()
    try:
        app_row = db.get(Application, application_id)
        if not app_row:
            return {"error": "application nahi mili"}
        job = db.get(Job, app_row.job_id)
        cand = db.get(Candidate, app_row.candidate_id)

        slot = find_free_slot(job.id)
        if not slot:
            emit(task_id, "HR", "error", "Koi free interview slot nahi bacha")
            return {"error": "no_slot", "message": "Admin ko slots add karne kehna"}

        slot_row = db.get(InterviewSlot, slot.id)
        slot_row.is_booked = True

        questions = generate_screening_questions(job.jd_markdown or job.title, job.id, task_id)

        interview = Interview(application_id=application_id, slot_id=slot_row.id,
                              questions=questions["questions"])
        db.add(interview)
        db.commit()
        db.refresh(interview)

        title = f"Interview - {job.title} - {cand.name or cand.email}"
        desc = (f"{job.title} interview at {settings.COMPANY_NAME}\n\n"
                f"Candidate: {cand.name} ({cand.email})\n"
                f"Screening score: {app_row.score}\n"
                f"{(app_row.reasoning or {}).get('one_liner', '')}")

        # --- A) asli Google Calendar event ---
        event = gcal.create_event(
            interviewer_email=slot_row.interviewer_email,
            candidate_email=cand.email,
            title=title, description=desc,
            start=slot_row.start_at, end=slot_row.end_at,
        )

        if event:
            interview.calendar_event_id = event["event_id"]
            interview.meeting_link = meeting_link or event["meet_link"] or event["html_link"]
            emit(task_id, "HR", "tool_call",
                 f"Google Calendar event bana ({slot_row.interviewer_email})",
                 {"event_id": event["event_id"], "meet": event["meet_link"]})
        else:
            # --- B) fallback: .ics ---
            interview.meeting_link = meeting_link or "Link email mein bheja jayega"
            interview.ics_path = _write_ics(
                interview.id, title, slot_row.start_at, slot_row.end_at,
                [cand.email, slot_row.interviewer_email], desc)

        app_row.status = "interview_scheduled"
        db.commit()

        ctx = {
            "candidate_name": cand.name or "there", "job_title": job.title,
            "company": settings.COMPANY_NAME,
            "when": slot_row.start_at.strftime("%d %b %Y, %H:%M UTC"),
            "meeting_link": interview.meeting_link,
            "interviewer": slot_row.interviewer_email,
        }
        # Calendar event bana to Google khud invite bhej chuka — hum sirf .ics case mein attach karte hain
        send_template(cand.email, "interview_invite", ctx,
                      attachment=interview.ics_path or None)
        send_template(slot_row.interviewer_email, "interviewer_brief",
                      {**ctx, "candidate_email": cand.email,
                       "one_liner": (app_row.reasoning or {}).get("one_liner", ""),
                       "questions": questions["questions"]})

        emit(task_id, "HR", "tool_call",
             f"Interview book ho gaya: {cand.email} @ {ctx['when']}",
             {"interview_id": interview.id})
        return {"interview_id": interview.id, "when": ctx["when"],
                "meeting_link": interview.meeting_link,
                "calendar": "google" if event else "ics",
                "questions_artifact": questions["artifact_id"]}
    finally:
        db.close()
