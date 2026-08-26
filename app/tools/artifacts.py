"""Har document artifact ban ke DB mein save hota hai aur uski ID return hoti hai."""
from app.database import db_session
from app.models import Artifact


def save_artifact(agent: str, type: str, title: str, content: str,
                  task_id: str | None = None, meta: dict | None = None) -> str:
    db = db_session()
    try:
        art = Artifact(agent=agent, type=type, title=title, content=content,
                       task_id=task_id, meta=meta or {})
        db.add(art)
        db.commit()
        db.refresh(art)
        return art.id
    finally:
        db.close()
