"""PUBLIC side — jobs dekhna (internal + external) aur live fetch karna."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job
from app.services.external_jobs import fetch_jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(source: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Job).filter(Job.status == "open")
    if source:
        query = query.filter(Job.source == source)
    if q:
        query = query.filter(Job.title.ilike(f"%{q}%"))
    return [{"id": j.id, "title": j.title, "company": j.company_name, "location": j.location,
             "source": j.source, "external_url": j.external_url,
             "apply_url": f"/api/jobs/{j.id}/apply"} for j in query.limit(100).all()]


@router.get("/search-live")
def search_live(q: str, limit: int = 20, providers: str | None = None):
    """DB ko chhue bagair seedha free job boards se — preview ke liye."""
    p = providers.split(",") if providers else None
    return fetch_jobs(q, limit, p)


@router.get("/{job_id}")
def job_detail(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job nahi mili")
    return {"id": job.id, "title": job.title, "company": job.company_name,
            "location": job.location, "type": job.employment_type, "source": job.source,
            "external_url": job.external_url, "jd": job.jd_markdown,
            "must_have": job.must_have_skills}
