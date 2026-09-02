# Calendar feature — kya kahan paste karna hai

## 1. Nayi files (seedha copy karein)
| File | Kahan |
|---|---|
| `google_calendar.py` | `app/services/google_calendar.py` |
| `calendar.py` | `app/routers/calendar.py` |
| `interview_tools.py` | `app/tools/interview_tools.py` (purani replace karein) |

## 2. `app/models.py` — sabse neeche yeh paste karein

```python
class CalendarCredential(Base):
    """Interviewer ka Google OAuth token. Ek baar connect, phir hamesha kaam karta hai."""
    __tablename__ = "calendar_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
```

Aur `class Interview` ke andar ek nayi line add karein (kisi bhi field ke neeche):

```python
    calendar_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

## 3. `app/config.py` — Settings class ke andar

```python
    # Google Calendar
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/calendar/callback"
```

## 4. `app/main.py` — router include karein

```python
from app.routers import admin, agent, applications, calendar, events, jobs
...
app.include_router(calendar.router)
```

## 5. `requirements.txt` mein add karein

```
google-auth==2.38.0
google-auth-oauthlib==1.2.1
google-api-python-client==2.157.0
```

## 6. `.env` mein add karein

```
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/calendar/callback
```

## 7. Purani DB mein naya column add karein (ek dafa)

```bash
python -c "from app.database import engine; from sqlalchemy import text; c=engine.connect(); c.execute(text('ALTER TABLE interviews ADD COLUMN calendar_event_id VARCHAR(200)')); c.commit(); print('column add ho gaya')"
```

Nayi table (`calendar_credentials`) khud ban jayegi server start pe.
