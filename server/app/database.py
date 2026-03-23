from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_papers_schema(engine) -> None:
    """Add columns introduced after first deploy (SQLite / Postgres)."""
    try:
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("papers")}
    except Exception:
        return
    if "citation_synced_at" in cols:
        return
    url = str(engine.url)
    with engine.begin() as conn:
        if "sqlite" in url:
            conn.execute(text("ALTER TABLE papers ADD COLUMN citation_synced_at DATETIME"))
        else:
            conn.execute(text("ALTER TABLE papers ADD COLUMN citation_synced_at TIMESTAMPTZ"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
