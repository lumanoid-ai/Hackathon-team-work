"""SQLAlchemy engine + session. SQLite se start karein, Postgres pe sirf URL badalna hai."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_session() -> Session:
    """Background tasks / scripts ke liye (manually close karein)."""
    return SessionLocal()


def init_db() -> None:
    from app import models  # noqa: F401  (models import hone zaroori hain)
    Base.metadata.create_all(bind=engine)
