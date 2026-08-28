"""
tools/calendar.py -- the Google Calendar tool.

This is a TOOL, not an agent. Any agent can import it:
  - the Scheduler agent uses it for meetings, birthdays, availability
  - the HR agent will import the same functions to book interviews

Set CALENDAR_MODE in your .env:
  mock   -> a local JSON file, no Google account needed. Build with this.
  google -> the real Google Calendar API.

Build everything in mock mode first. Getting OAuth working is a separate
job from getting your agent working -- do not do both at once.
"""

import os
import json
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("CALENDAR_MODE", "mock").lower()
MOCK_FILE = "mock_calendar.json"
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

WORK_START_HOUR = 9
WORK_END_HOUR = 17


# ====================================================================
# PUBLIC FUNCTIONS -- these are what your agents call
# ====================================================================

def list_events(days_ahead: int = 7) -> list[dict]:
    """Everything on the calendar between now and N days from now."""
    start = _now()
    end = start + timedelta(days=days_ahead)
    events = _google_list(start, end) if MODE == "google" else _mock_list(start, end)
    return sorted(events, key=lambda e: e["start"])


def find_free_slots(duration_minutes: int = 60,
                    days_ahead: int = 7,
                    max_slots: int = 5) -> list[dict]:
    """
    Open slots during working hours, in order.

    We compute this ourselves from the busy list rather than using Google's
    freeBusy endpoint -- fewer API calls, and it works identically in mock
    mode so you can test the whole flow offline.
    """
    busy = [(_parse(e["start"]), _parse(e["end"])) for e in list_events(days_ahead)]
    slots = []
    cursor = _now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    limit = _now() + timedelta(days=days_ahead)

    while cursor < limit and len(slots) < max_slots:
        # Skip nights and weekends
        if cursor.weekday() >= 5 or not (WORK_START_HOUR <= cursor.hour < WORK_END_HOUR):
            cursor += timedelta(hours=1)
            continue

        slot_end = cursor + timedelta(minutes=duration_minutes)
        overlaps = any(cursor < b_end and slot_end > b_start for b_start, b_end in busy)

        if not overlaps and slot_end.hour <= WORK_END_HOUR:
            slots.append({
                "start": cursor.isoformat(),
                "end": slot_end.isoformat(),
                "label": cursor.strftime("%a %d %b, %I:%M %p"),
            })
            cursor += timedelta(minutes=duration_minutes)
        else:
            cursor += timedelta(hours=1)

    return slots


def create_event(title: str,
                 start_iso: str,
                 duration_minutes: int = 60,
                 attendees: list[str] | None = None,
                 description: str = "") -> dict:
    """
    Put something on the calendar.

    IMPORTANT: never let an agent call this without the user confirming
    first. Writing to someone's real calendar unasked is the fastest way
    to lose their trust in the whole product.
    """
    start = _parse(start_iso)
    end = start + timedelta(minutes=duration_minutes)
    event = {
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "attendees": attendees or [],
        "description": description,
    }
    return _google_create(event) if MODE == "google" else _mock_create(event)


def upcoming_people_events(days_ahead: int = 30) -> list[dict]:
    """
    Birthdays and work anniversaries coming up.

    We find these by keyword. Real calendars are messy, and a keyword match
    is more reliable here than trying to be clever about event types.
    """
    keywords = ("birthday", "anniversary", "bday", "joined", "work anniversary")
    return [
        e for e in list_events(days_ahead)
        if any(k in e["title"].lower() for k in keywords)
    ]


# ====================================================================
# MOCK BACKEND -- a JSON file on disk
# ====================================================================

def _mock_store() -> list[dict]:
    if not os.path.exists(MOCK_FILE):
        _seed_mock()
    with open(MOCK_FILE, encoding="utf-8") as f:
        return json.load(f)


def _mock_list(start: datetime, end: datetime) -> list[dict]:
    return [e for e in _mock_store() if start <= _parse(e["start"]) <= end]


def _mock_create(event: dict) -> dict:
    store = _mock_store()
    store.append(event)
    with open(MOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    return {"created": True, "event": event, "mode": "mock"}


def _seed_mock():
    """Believable starting calendar so your demo isn't empty."""
    base = _now().replace(hour=10, minute=0, second=0, microsecond=0)

    def at(day_offset, hour, minutes=60):
        s = base + timedelta(days=day_offset)
        s = s.replace(hour=hour)
        return s.isoformat(), (s + timedelta(minutes=minutes)).isoformat()

    seed = []
    for day, hour, title in [
        (1, 10, "Standup"),
        (1, 14, "Interview: Sara K. -- Backend Engineer"),
        (2, 11, "Sara's birthday"),
        (3, 15, "Q3 board review"),
        (4, 9, "Interview: Bilal A. -- Backend Engineer"),
        (6, 10, "Ahmed work anniversary (3 years)"),
        (8, 13, "Onboarding: new hire day 1"),
    ]:
        s, e = at(day, hour)
        seed.append({"title": title, "start": s, "end": e,
                     "attendees": [], "description": ""})

    with open(MOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2)


# ====================================================================
# GOOGLE BACKEND -- the real thing
# ====================================================================

def _service():
    """
    Builds an authenticated Google Calendar client.

    First run opens a browser window asking you to log in, then saves
    token.json so you never have to do it again.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _google_list(start: datetime, end: datetime) -> list[dict]:
    result = _service().events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for item in result.get("items", []):
        s = item["start"].get("dateTime") or item["start"].get("date")
        e = item["end"].get("dateTime") or item["end"].get("date")
        events.append({
            "title": item.get("summary", "(no title)"),
            "start": s,
            "end": e,
            "attendees": [a.get("email", "") for a in item.get("attendees", [])],
            "description": item.get("description", ""),
        })
    return events


def _google_create(event: dict) -> dict:
    body = {
        "summary": event["title"],
        "description": event["description"],
        "start": {"dateTime": event["start"]},
        "end": {"dateTime": event["end"]},
    }
    if event["attendees"]:
        body["attendees"] = [{"email": a} for a in event["attendees"]]

    created = _service().events().insert(calendarId=CALENDAR_ID, body=body).execute()
    return {"created": True, "event": event, "mode": "google",
            "link": created.get("htmlLink", "")}


# ====================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=_now().tzinfo)
