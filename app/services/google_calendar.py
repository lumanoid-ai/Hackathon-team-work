"""Google Calendar OAuth 2.0 + event creation.

Free hai — Google Calendar API ka koi charge nahi.
Do cheezein karta hai:
  1. Interviewer apna calendar connect karta hai (OAuth, ek baar)
  2. Agent us calendar mein asli event banata hai + Google Meet link + invite

Agar interviewer connected nahi hai to code chup-chaap .ics fallback pe chala jata hai.
"""
import secrets
from datetime import datetime, timedelta

from app.config import settings
from app.database import db_session
from app.models import CalendarCredential

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",   # event banane ke liye
    "https://www.googleapis.com/auth/calendar.readonly",  # free/busy check ke liye
    "https://www.googleapis.com/auth/userinfo.email",     # kis ka calendar hai
    "openid",
]

# CSRF protection — connect shuru karte waqt state yahan rakhte hain
_pending_states: set[str] = set()


def enabled() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


# ---------------------------------------------------------------- OAuth flow
def build_auth_url() -> str:
    """Step 1 — interviewer ko yeh URL bhejein, wo Google pe login karega."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES,
                                   redirect_uri=settings.GOOGLE_REDIRECT_URI)
    state = secrets.token_urlsafe(24)
    _pending_states.add(state)
    url, _ = flow.authorization_url(
        access_type="offline",       # refresh_token milega — warna 1 ghante baad expire
        prompt="consent",            # har baar refresh_token milta rahe
        include_granted_scopes="true",
        state=state,
    )
    return url


def exchange_code(code: str, state: str) -> dict:
    """Step 2 — Google callback pe code bhejta hai, hum usay token mein badalte hain."""
    from google_auth_oauthlib.flow import Flow

    if state not in _pending_states:
        raise ValueError("State match nahi hui (CSRF check fail). Dobara connect karein.")
    _pending_states.discard(state)

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES,
                                   redirect_uri=settings.GOOGLE_REDIRECT_URI)
    flow.fetch_token(code=code)
    creds = flow.credentials

    email = _fetch_email(creds)
    _save(email, creds)
    return {"email": email, "connected": True}


def _fetch_email(creds) -> str:
    from googleapiclient.discovery import build

    info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
    return info["email"]


def _save(email: str, creds) -> None:
    db = db_session()
    try:
        row = db.query(CalendarCredential).filter(
            CalendarCredential.email == email).first()
        if not row:
            row = CalendarCredential(email=email)
            db.add(row)
        row.token = creds.token
        # refresh_token sirf pehli dafa milta hai — purana mat mitao
        if creds.refresh_token:
            row.refresh_token = creds.refresh_token
        row.scopes = list(creds.scopes or SCOPES)
        row.expiry = creds.expiry
        db.commit()
    finally:
        db.close()


def get_credentials(email: str):
    """Saved token uthao, expire ho gaya ho to khud refresh kar lo."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    db = db_session()
    try:
        row = db.query(CalendarCredential).filter(
            CalendarCredential.email == email).first()
        if not row or not row.refresh_token:
            return None
        creds = Credentials(
            token=row.token,
            refresh_token=row.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=row.scopes or SCOPES,
        )
        if not creds.valid:
            creds.refresh(Request())
            row.token = creds.token
            row.expiry = creds.expiry
            db.commit()
        return creds
    except Exception as e:
        print(f"[calendar] {email} ka token refresh fail: {e}")
        return None
    finally:
        db.close()


def is_connected(email: str) -> bool:
    db = db_session()
    try:
        row = db.query(CalendarCredential).filter(
            CalendarCredential.email == email).first()
        return bool(row and row.refresh_token)
    finally:
        db.close()


def disconnect(email: str) -> bool:
    db = db_session()
    try:
        n = db.query(CalendarCredential).filter(
            CalendarCredential.email == email).delete()
        db.commit()
        return n > 0
    finally:
        db.close()


# ---------------------------------------------------------------- Calendar ops
def _rfc3339(dt: datetime) -> str:
    """Hamare datetimes naive UTC hain — Google ko 'Z' suffix chahiye."""
    return dt.replace(microsecond=0).isoformat() + "Z"


def is_free(email: str, start: datetime, end: datetime) -> bool:
    """Free/busy check — interviewer ka calendar us waqt khali hai ya nahi.
    Connected na ho to True (yaani rok mat lagao)."""
    from googleapiclient.discovery import build

    creds = get_credentials(email)
    if not creds:
        return True
    try:
        service = build("calendar", "v3", credentials=creds)
        result = service.freebusy().query(body={
            "timeMin": _rfc3339(start),
            "timeMax": _rfc3339(end),
            "items": [{"id": "primary"}],
        }).execute()
        busy = result["calendars"]["primary"].get("busy", [])
        return len(busy) == 0
    except Exception as e:
        print(f"[calendar] freebusy fail ({email}): {e}")
        return True


def create_event(interviewer_email: str, candidate_email: str, title: str,
                 description: str, start: datetime, end: datetime,
                 with_meet: bool = True) -> dict | None:
    """Asli calendar event banao. Google khud dono ko invite email bhej dega.

    Return: {"event_id","html_link","meet_link"} ya None (fallback .ics chalega)
    """
    from googleapiclient.discovery import build

    creds = get_credentials(interviewer_email)
    if not creds:
        return None

    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": _rfc3339(start), "timeZone": "UTC"},
        "end": {"dateTime": _rfc3339(end), "timeZone": "UTC"},
        "attendees": [{"email": candidate_email}, {"email": interviewer_email}],
        "reminders": {"useDefault": False, "overrides": [
            {"method": "email", "minutes": 24 * 60},
            {"method": "popup", "minutes": 30},
        ]},
    }
    if with_meet:
        body["conferenceData"] = {"createRequest": {
            "requestId": secrets.token_hex(8),
            "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }}

    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(
            calendarId="primary",
            body=body,
            conferenceDataVersion=1 if with_meet else 0,
            sendUpdates="all",          # Google khud invite email bhejega
        ).execute()

        meet = ""
        for ep in (event.get("conferenceData", {}).get("entryPoints") or []):
            if ep.get("entryPointType") == "video":
                meet = ep.get("uri", "")
                break

        return {"event_id": event["id"], "html_link": event.get("htmlLink", ""),
                "meet_link": meet or event.get("hangoutLink", "")}
    except Exception as e:
        print(f"[calendar] event banane mein fail: {e}")
        return None


def cancel_event(interviewer_email: str, event_id: str) -> bool:
    from googleapiclient.discovery import build

    creds = get_credentials(interviewer_email)
    if not creds:
        return False
    try:
        build("calendar", "v3", credentials=creds).events().delete(
            calendarId="primary", eventId=event_id, sendUpdates="all").execute()
        return True
    except Exception as e:
        print(f"[calendar] cancel fail: {e}")
        return False
