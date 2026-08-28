"""
agents/scheduler.py -- the Scheduler agent. This one is YOURS.

It owns the calendar. The Manager delegates anything about time to it:
meetings, interviews, availability, birthdays, deadlines.

It follows exactly the same shape as every other agent -- name, color,
role, run() -- so the Manager doesn't need any special handling for it.

HOW IT WORKS (same pipeline idea as the Manager):
  1. ROUTE  -- ask the AI which calendar action this is + pull out params
  2. ACT    -- call the plain Python calendar function
  3. REPORT -- turn the result into readable text for the Manager

The AI never touches the calendar directly. It only picks the action.
That means it can never hallucinate a meeting that doesn't exist.
"""

from llm import ask_json
from events import emit
from tools import calendar


ROUTE_PROMPT = """You handle calendar requests. Pick ONE action.

Actions:
- list_events    : "what's on my calendar", "what's this week", upcoming schedule
- find_slots     : "when am I free", "find time for", scheduling availability
- book           : "schedule X", "book an interview", "put it in the calendar"
- people_events  : birthdays, work anniversaries, "whose birthday is coming up"

Return ONLY valid JSON, no markdown:
{"action": "list_events", "params": {"days_ahead": 7}}

Params by action:
  list_events   -> {"days_ahead": int}
  find_slots    -> {"duration_minutes": int, "days_ahead": int}
  book          -> {"title": str, "start_iso": str, "duration_minutes": int}
  people_events -> {"days_ahead": int}

If a value isn't stated, use sensible defaults (7 days, 60 minutes)."""


class SchedulerAgent:

    name = "Scheduler"
    color = "#EF9F27"
    role = ("calendar, meetings, interview scheduling, availability, "
            "deadlines, birthdays and work anniversaries")

    def run(self, subtask: str, context: dict, task_id: str) -> str:
        emit(task_id, self.name, "thinking", f"Checking the calendar: {subtask[:50]}")

        # STEP 1 -- decide what kind of calendar request this is
        try:
            decision = ask_json(ROUTE_PROMPT, f"Request: {subtask}")
            action = decision.get("action", "list_events")
            params = decision.get("params", {})
        except Exception as e:
            emit(task_id, self.name, "error", f"Routing failed: {e}")
            action, params = "list_events", {}

        emit(task_id, self.name, "tool_call", f"calendar.{action}")

        # STEP 2 -- run the real function
        try:
            if action == "find_slots":
                result = calendar.find_free_slots(
                    duration_minutes=params.get("duration_minutes", 60),
                    days_ahead=params.get("days_ahead", 7),
                )
                text = self._format_slots(result)

            elif action == "book":
                # NEVER write to a real calendar without asking first.
                text = self._propose_booking(params, task_id)

            elif action == "people_events":
                result = calendar.upcoming_people_events(
                    days_ahead=params.get("days_ahead", 30))
                text = self._format_events(result, "No birthdays or anniversaries coming up.")

            else:
                result = calendar.list_events(days_ahead=params.get("days_ahead", 7))
                text = self._format_events(result, "The calendar is clear.")

        except Exception as e:
            emit(task_id, self.name, "error", str(e))
            return f"Could not read the calendar: {e}"

        emit(task_id, self.name, "done", "Calendar checked")
        return text

    # ------------------------------------------------------------------

    def confirm_booking(self, title: str, start_iso: str,
                        duration_minutes: int = 60,
                        attendees: list[str] | None = None) -> str:
        """
        Actually writes the event. Call this ONLY after the user has
        clicked confirm in the UI -- never straight from run().
        """
        outcome = calendar.create_event(title, start_iso, duration_minutes, attendees)
        return f"Booked: {title} on {outcome['event']['start'][:16].replace('T', ' at ')}"

    # ------------------------------------------------------------------

    def _propose_booking(self, params: dict, task_id: str) -> str:
        title = params.get("title", "New meeting")
        duration = params.get("duration_minutes", 60)
        start = params.get("start_iso")

        if not start:
            slots = calendar.find_free_slots(duration_minutes=duration)
            if not slots:
                return f"No free slots for '{title}' in the next 7 days."
            start = slots[0]["start"]

        emit(task_id, self.name, "artifact", "Booking awaiting confirmation",
             {"type": "booking_proposal", "title": title,
              "start_iso": start, "duration_minutes": duration})

        when = start[:16].replace("T", " at ")
        return (f"Ready to book '{title}' for {when} ({duration} min). "
                f"Waiting for the user to confirm before writing to the calendar.")

    def _format_events(self, events: list[dict], empty_message: str) -> str:
        if not events:
            return empty_message
        lines = [f"- {e['start'][:16].replace('T', ' at ')} -- {e['title']}"
                 for e in events]
        return f"{len(events)} item(s) on the calendar:\n" + "\n".join(lines)

    def _format_slots(self, slots: list[dict]) -> str:
        if not slots:
            return "No free slots during working hours in that window."
        return "Open slots:\n" + "\n".join(f"- {s['label']}" for s in slots)


scheduler_agent = SchedulerAgent()
