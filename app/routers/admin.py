"""ADMIN side — job create karna, slots dena, handbook upload, candidates dekhna."""
import os
import shutil

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Application, Artifact, Candidate, EmailLog, InterviewSlot, Job, Workspace
from app.schemas import ImportJobsIn, InterviewResultIn, JobIn, OfferIn, SlotIn, WorkspaceIn
from app.services.application_service import make_offer, mark_interviewed
from app.services.job_service import create_job, import_external_jobs
from app.tools.jd_tools import write_jd
from app.tools.policy_tools import index_handbook

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(x_admin_key: str = Header(default="")):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(401, "Admin key galat hai (header: X-Admin-Key)")


@router.post("/workspaces", dependencies=[Depends(require_admin)])
def new_workspace(body: WorkspaceIn, db: Session = Depends(get_db)):
    ws = Workspace(name=body.name, context=body.context)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return {"id": ws.id, "name": ws.name}


@router.post("/jobs", dependencies=[Depends(require_admin)])
def admin_create_job(body: JobIn, db: Session = Depends(get_db)):
    """Admin job banata hai; HR agent turant JD likh deta hai."""
    job = create_job(body.workspace_id, body.title, body.seniority, body.location,
                     body.employment_type, body.must_have, body.nice_to_have)
    jd = None
    if body.generate_jd:
        ws = db.get(Workspace, body.workspace_id)
        jd = write_jd(role=body.title, seniority=body.seniority,
                      must_have_skills=body.must_have, nice_to_have_skills=body.nice_to_have,
                      location=body.location, employment_type=body.employment_type,
                      company_context=ws.context if ws else "", job_id=job.id)
    return {"job_id": job.id, "status": "open" if jd else "draft",
            "jd_artifact": jd["artifact_id"] if jd else None,
            "apply_url": f"/api/jobs/{job.id}/apply"}


@router.post("/jobs/import", dependencies=[Depends(require_admin)])
def admin_import_jobs(body: ImportJobsIn):
    return import_external_jobs(body.workspace_id, body.query, body.limit, body.providers)


@router.post("/slots", dependencies=[Depends(require_admin)])
def add_slot(body: SlotIn, db: Session = Depends(get_db)):
    slot = InterviewSlot(interviewer_email=body.interviewer_email, start_at=body.start_at,
                         end_at=body.end_at, job_id=body.job_id)
    db.add(slot)
    db.commit()
    return {"slot_id": slot.id}


@router.post("/handbook", dependencies=[Depends(require_admin)])
async def upload_handbook(file: UploadFile = File(...), workspace_id: str = Form(None)):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return index_handbook(path, file.filename, workspace_id)


@router.get("/jobs/{job_id}/candidates", dependencies=[Depends(require_admin)])
def job_candidates(job_id: str, db: Session = Depends(get_db)):
    """Wohi ranked list jo frontend baad mein render karegi."""
    rows = (db.query(Application, Candidate)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .filter(Application.job_id == job_id)
            .order_by(Application.score.desc().nullslast()).all())
    return [{
        "application_id": a.id, "name": c.name, "email": c.email,
        "score": a.score, "verdict": a.verdict, "status": a.status,
        "years": (c.parsed or {}).get("years_experience"),
        "skills": (c.parsed or {}).get("skills", [])[:6],
        **(a.reasoning or {}),
    } for a, c in rows]


@router.post("/interviews/result", dependencies=[Depends(require_admin)])
def interview_result(body: InterviewResultIn):
    return mark_interviewed(body.application_id, body.passed, body.note)


@router.post("/offer", dependencies=[Depends(require_admin)])
def offer(body: OfferIn):
    return make_offer(body.application_id, body.start_date, body.note)


@router.get("/artifacts/{artifact_id}", dependencies=[Depends(require_admin)])
def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    art = db.get(Artifact, artifact_id)
    if not art:
        raise HTTPException(404, "artifact nahi mila")
    return {"id": art.id, "type": art.type, "title": art.title,
            "content": art.content, "meta": art.meta}


@router.get("/emails", dependencies=[Depends(require_admin)])
def emails(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(EmailLog).order_by(EmailLog.id.desc()).limit(limit).all()
    return [{"to": e.to_email, "subject": e.subject, "template": e.template,
             "status": e.status, "at": e.created_at} for e in rows]
