"""Live activity feed (SSE). Frontend baad mein isay seedha consume kar lega."""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.events import subscribe, unsubscribe
from app.database import get_db
from app.models import Event

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def recent(task_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(Event).order_by(Event.id.desc())
    if task_id:
        q = q.filter(Event.task_id == task_id)
    return [{"id": e.id, "task_id": e.task_id, "agent": e.agent, "type": e.type,
             "message": e.message, "payload": e.payload, "at": e.created_at}
            for e in q.limit(limit).all()][::-1]


@router.get("/stream")
async def stream():
    q = subscribe()

    async def gen():
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(evt, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
