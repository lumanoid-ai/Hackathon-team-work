"""Event stream. Every step emits, so the Manager can see what is happening."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

EventType = Literal["tool_call", "thinking", "result", "error"]


@dataclass
class Event:
    type: EventType
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventStream:
    """Collects events and optionally forwards them to a live listener."""

    def __init__(self, listener: Callable[[Event], None] | None = None):
        self.events: list[Event] = []
        self._listener = listener

    def emit(self, type: EventType, message: str, **payload: Any) -> None:
        event = Event(type=type, message=message, payload=payload)
        self.events.append(event)
        if self._listener:
            self._listener(event)

    def to_list(self) -> list[dict]:
        return [
            {"type": e.type, "message": e.message, "payload": e.payload}
            for e in self.events
        ]


def print_listener(event: Event) -> None:
    """Default listener for local runs."""
    print(f"[{event.type}] {event.message}")
