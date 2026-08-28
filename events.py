"""
events.py -- every action any agent takes gets recorded here.

WHY THIS MATTERS: the frontend shows a live activity feed and an animated
delegation tree. Both are built entirely from these events. If agents don't
emit events, the UI has nothing to show and your demo looks dead.

Emit early, emit often.
"""

from datetime import datetime, timezone

# task_id -> list of events. In-memory is fine for a hackathon.
EVENT_LOG: dict[str, list[dict]] = {}


def emit(task_id: str,
         agent: str,
         type: str,
         message: str,
         payload: dict | None = None) -> dict:
    """
    Record one event.

    type must be one of:
      thinking    -- agent is reasoning (show in activity feed)
      delegation  -- agent handed work to another agent (draws a tree edge)
      tool_call   -- agent used a tool
      artifact    -- agent produced a document/chart
      done        -- agent finished
      error       -- something broke
    """
    event = {
        "task_id": task_id,
        "agent": agent,
        "type": type,
        "message": message,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    EVENT_LOG.setdefault(task_id, []).append(event)

    # Print to terminal so you can see what's happening while you build
    icon = {"thinking": "..", "delegation": "->", "tool_call": "[]",
            "artifact": "[]", "done": "OK", "error": "!!"}.get(type, "  ")
    print(f"  {icon} [{agent}] {message}")

    return event


def get_events(task_id: str) -> list[dict]:
    return EVENT_LOG.get(task_id, [])
