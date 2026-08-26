"""Candidate apply karta hai. Resume upload -> pipeline start."""
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Application, Candidate, Job
from app.services.application_service import create_application, screen_application

router = APIRouter(prefix="/api", tags=["applications"])

ALLOWED = {".pdf", ".docx", ".txt"}


@router.post("/jobs/{job_id}/apply")
async def apply(job_id: str, background: BackgroundTasks,
                name: str = Form(...), email: str = Form(...),
                phone: str = Form(""), cover_note: str = Form(""),
                resume: UploadFile = File(...), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "open":
        raise HTTPException(404, "Job open nahi hai")

    ext = os.path.splitext(resume.filename)[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Sirf {', '.join(ALLOWED)} allowed hain")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    res = create_application(job_id, email, name, path, phone, cover_note)
    if res.get("error"):
        raise HTTPException(400, res["error"])

    # screening turant background mein (scheduler bhi safety net hai)
    if not res.get("duplicate"):
        background.add_task(screen_application, res["application_id"])

    return {**res, "message": "Application mil gayi — confirmation email bhej diya hai."}


@router.get("/applications/{application_id}")
def status(application_id: str, db: Session = Depends(get_db)):
    a = db.get(Application, application_id)
    if not a:
        raise HTTPException(404, "nahi mili")
    c = db.get(Candidate, a.candidate_id)
    j = db.get(Job, a.job_id)
    return {"application_id": a.id, "job": j.title, "candidate": c.email,
            "status": a.status, "score": a.score, "updated_at": a.updated_at}
