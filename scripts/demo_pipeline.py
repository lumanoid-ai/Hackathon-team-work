"""Poora end-to-end demo bina UI ke:
resumes -> applications -> auto screening -> emails -> interview booking.

Chalao:  python -m scripts.demo_pipeline <JOB_ID>
"""
import glob
import sys

from app.database import init_db
from app.services.application_service import create_application, screen_application


def main(job_id: str):
    init_db()
    files = sorted(glob.glob("./data/resumes/*.pdf"))
    if not files:
        print("Pehle chalao: python -m scripts.seed_resumes")
        return
    for i, f in enumerate(files, 1):
        email = f"candidate{i}@example.com"
        res = create_application(job_id, email, f"Candidate {i}", f)
        print(f"[{i}] apply -> {res}")
        out = screen_application(res["application_id"])
        print(f"    screen -> score={out.get('score')} status={out.get('status')}")


if __name__ == "__main__":
    main(sys.argv[1])
