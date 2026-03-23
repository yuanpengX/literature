from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_user_subscription_columns(engine) -> None:
    try:
        insp = inspect(engine)
        if not insp.has_table("user_profiles"):
            return
        cols = {c["name"] for c in insp.get_columns("user_profiles")}
    except Exception:
        return
    url = str(engine.url)
    with engine.begin() as conn:
        if "subscription_keywords_json" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_profiles ADD COLUMN subscription_keywords_json TEXT DEFAULT '[]'"
                )
            )
        if "subscription_journals_json" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_profiles ADD COLUMN subscription_journals_json TEXT DEFAULT '[]'"
                )
            )
        if "subscription_conferences_json" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user_profiles ADD COLUMN subscription_conferences_json TEXT DEFAULT '[]'"
                )
            )


def ensure_user_llm_columns(engine) -> None:
    try:
        insp = inspect(engine)
        if not insp.has_table("user_profiles"):
            return
        cols = {c["name"] for c in insp.get_columns("user_profiles")}
    except Exception:
        return
    url = str(engine.url)
    with engine.begin() as conn:
        if "llm_base_url" not in cols:
            if "sqlite" in url:
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN llm_base_url TEXT DEFAULT ''"))
            else:
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN llm_base_url TEXT DEFAULT ''"))
        if "llm_api_key" not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN llm_api_key TEXT DEFAULT ''"))
        if "llm_model" not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN llm_model TEXT DEFAULT ''"))


def ensure_papers_schema(engine) -> None:
    """Add columns introduced after first deploy (SQLite / Postgres)."""
    try:
        insp = inspect(engine)
        if not insp.has_table("papers"):
            return
        cols = {c["name"] for c in insp.get_columns("papers")}
    except Exception:
        return
    url = str(engine.url)
    is_sqlite = "sqlite" in url
    with engine.begin() as conn:
        if "citation_synced_at" not in cols:
            if is_sqlite:
                conn.execute(text("ALTER TABLE papers ADD COLUMN citation_synced_at DATETIME"))
            else:
                conn.execute(text("ALTER TABLE papers ADD COLUMN citation_synced_at TIMESTAMPTZ"))
        if "authors_text" not in cols:
            conn.execute(text("ALTER TABLE papers ADD COLUMN authors_text TEXT DEFAULT ''"))
        if "openalex_source_key" not in cols:
            conn.execute(text("ALTER TABLE papers ADD COLUMN openalex_source_key VARCHAR(32)"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
