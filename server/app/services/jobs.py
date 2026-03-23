from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AnalyticsEvent, Paper
from app.services.ingest import run_all_ingestion


def purge_old_papers(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.paper_ttl_days)
    res = db.execute(delete(Paper).where(Paper.ingested_at < cutoff))
    db.commit()
    return res.rowcount or 0


def purge_old_events(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.event_ttl_days)
    res = db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.created_at < cutoff))
    db.commit()
    return res.rowcount or 0


def scheduled_ingest(db: Session) -> dict:
    return run_all_ingestion(db)
