"""Saari settings ek jagah. Kahin bhi os.getenv() mat likhna."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_EMBED_MODEL: str = "models/text-embedding-004"

    # DB
    DATABASE_URL: str = "sqlite:///./data/hr.db"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM_NAME: str = "Talent Team"
    HR_INBOX: str = ""

    # Business rules
    COMPANY_NAME: str = "Luminoid AI"
    SHORTLIST_THRESHOLD: int = 75
    HOLD_THRESHOLD: int = 55
    AUTO_SCHEDULE_INTERVIEW: bool = True
    ADMIN_API_KEY: str = "change-me-admin-key"

    # Job sync
    JOB_SYNC_ENABLED: bool = True
    JOB_SYNC_QUERIES: str = "python developer,data analyst"

    # Paths
    UPLOAD_DIR: str = "./data/uploads"
    ICS_DIR: str = "./data/ics"
    CHROMA_DIR: str = "./data/chroma"

    # Google Calendar
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/calendar/callback"

    @property
    def sync_queries(self) -> list[str]:
        return [q.strip() for q in self.JOB_SYNC_QUERIES.split(",") if q.strip()]


settings = Settings()
