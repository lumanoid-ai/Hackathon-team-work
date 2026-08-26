"""Event bus: har agent action DB mein bhi jata hai aur live subscribers ko bhi."""
import asyncio
from typing import Any

from app.database import db_session
from app.models import Event

_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def emit(task_id: str | None, agent: str, type: str, message: str,
         payload: dict[str, Any] | None = None) -> dict:
    """Spec ke mutabiq event shape:
    {"task_id":"task_42","agent":"HR","type":"tool_call","message":"...","payload":{}}
    """
    payload = payload or {}
    db = db_session()
    try:
        row = Event(task_id=task_id, agent=agent, type=type, message=message, payload=payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        evt = {
            "id": row.id, "task_id": task_id, "agent": agent, "type": type,
            "message": message, "payload": payload,
            "created_at": row.created_at.isoformat(),
        }
    finally:
        db.close()

    print(f"[{agent}] {type}: {message}")
    for q in list(_subscribers):
        try:
            q.put_nowait(evt)
        except asyncio.QueueFull:
            pass
    return evt
