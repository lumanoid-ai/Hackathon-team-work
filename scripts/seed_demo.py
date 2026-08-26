"""Demo data: workspace + job + JD + interview slots.

Chalao:  python -m scripts.seed_demo
"""
from datetime import datetime, timedelta

from app.database import db_session, init_db
from app.models import InterviewSlot, Workspace
from app.services.job_service import create_job
from app.tools.jd_tools import write_jd

CONTEXT = """Acme Technologies Karachi-based ek 40-logon ki product company hai jo
logistics ke liye real-time tracking platform banati hai. Hum remote-first hain,
Pakistan aur UAE mein hire karte hain, aur 4-day release cycle chalate hain."""


def main():
    init_db()
    db = db_session()
    ws = Workspace(name="Acme Technologies", context=CONTEXT)
    db.add(ws); db.commit(); db.refresh(ws)
    ws_id = ws.id

    # interview slots: agle 10 din, roz 3 slots
    base = datetime.utcnow() + timedelta(days=1)
    for d in range(10):
        for h in (10, 13, 16):
            s = base.replace(hour=h, minute=0, second=0, microsecond=0) + timedelta(days=d)
            db.add(InterviewSlot(interviewer_email="hiring.manager@example.com",
                                 start_at=s, end_at=s + timedelta(minutes=45)))
    db.commit(); db.close()

    job = create_job(ws_id, "Backend Engineer", "mid", "Remote (PK)", "Full-time",
                     must_have=["Python", "PostgreSQL", "REST APIs", "Docker"],
                     nice_to_have=["AWS", "Kafka"], company_name="Acme Technologies")
    jd = write_jd(role="Backend Engineer", seniority="mid",
                  must_have_skills=["Python", "PostgreSQL", "REST APIs", "Docker"],
                  nice_to_have_skills=["AWS", "Kafka"], location="Remote (PK)",
                  company_context=CONTEXT, job_id=job.id)

    print(f"WORKSPACE_ID = {ws_id}")
    print(f"JOB_ID       = {job.id}")
    print(f"JD_ARTIFACT  = {jd['artifact_id']}")
    print("30 interview slots ban gaye.")


if __name__ == "__main__":
    main()
