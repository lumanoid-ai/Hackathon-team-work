"""Internal jobs create karna + external jobs ko apne DB mein import karna."""
from app.database import db_session
from app.models import Job
from app.services.external_jobs import fetch_jobs


def create_job(workspace_id: str, title: str, seniority: str = "mid",
               location: str = "Remote", employment_type: str = "Full-time",
               must_have: list[str] | None = None, nice_to_have: list[str] | None = None,
               company_name: str | None = None) -> Job:
    db = db_session()
    try:
        job = Job(workspace_id=workspace_id, title=title, seniority=seniority,
                  location=location, employment_type=employment_type,
                  must_have_skills=must_have or [], nice_to_have_skills=nice_to_have or [],
                  company_name=company_name, status="draft", source="internal")
        db.add(job)
        db.commit()
        db.refresh(job)
        db.expunge(job)
        return job
    finally:
        db.close()


def import_external_jobs(workspace_id: str, query: str, limit: int = 20,
                         providers: list[str] | None = None) -> dict:
    """Fetched jobs ko Job table mein daal deta hai taake unpe wohi apply-pipeline chale."""
    rows = fetch_jobs(query, limit, providers)
    db = db_session()
    created, skipped = [], 0
    try:
        for r in rows:
            exists = db.query(Job).filter(
                Job.source == r["source"], Job.external_id == r["external_id"]).first()
            if exists:
                skipped += 1
                continue
            job = Job(
                workspace_id=workspace_id, title=r["title"], location=r["location"],
                employment_type=r["employment_type"], jd_markdown=r["description"],
                status="open", source=r["source"], external_id=r["external_id"],
                external_url=r["url"], company_name=r["company_name"],
                must_have_skills=r.get("tags", [])[:8],
            )
            db.add(job)
            db.flush()
            created.append(job.id)
        db.commit()
    finally:
        db.close()
    return {"query": query, "fetched": len(rows), "imported": len(created), "skipped": skipped,
            "job_ids": created}
