import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import httpx
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.presets import CONFERENCE_PRESETS, JOURNAL_PRESETS
from app.config import settings
from app.models import Paper, UserProfile
from app.database import SessionLocal
from app.services.openalex import (
    enrich_arxiv_citations,
    fetch_and_upsert_openalex,
    fetch_and_upsert_openalex_conference_works,
    fetch_and_upsert_openalex_for_source_ids,
    normalize_openalex_source_id,
)

logger = logging.getLogger(__name__)

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    m = re.search(r"arxiv\.org/abs/([^?#]+)", entry_id, re.I)
    if m:
        return f"arxiv:{m.group(1)}"
    return f"arxiv:{entry_id[-32:]}"


def fetch_and_upsert_arxiv(db: Session) -> int:
    """Pull arXiv Atom API and upsert papers. Returns count of new rows."""
    params = {
        "search_query": settings.arxiv_query,
        "sortBy": "submittedDate",
        "max_results": settings.arxiv_max_results,
    }
    url = "https://export.arxiv.org/api/query"
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        root = ET.fromstring(r.text)

    count = 0
    for entry in root.findall("atom:entry", ARXIV_NS):
        id_el = entry.find("atom:id", ARXIV_NS)
        title_el = entry.find("atom:title", ARXIV_NS)
        summary_el = entry.find("atom:summary", ARXIV_NS)
        published_el = entry.find("atom:published", ARXIV_NS)
        if id_el is None or title_el is None:
            continue
        ext_id = _arxiv_id_from_entry_id((id_el.text or "").strip())
        title = " ".join((title_el.text or "").split())
        abstract = " ".join((summary_el.text or "").split()) if summary_el is not None else ""
        published = None
        if published_el is not None and published_el.text:
            published = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))

        pdf_url = None
        html_url = None
        primary = None
        for cat in entry.findall("atom:category", ARXIV_NS):
            term = cat.get("term")
            if term and primary is None:
                primary = term
        for link in entry.findall("atom:link", ARXIV_NS):
            href = link.get("href")
            typ = link.get("type", "")
            if typ == "application/pdf" and href:
                pdf_url = href
            elif link.get("rel") == "alternate" and href:
                html_url = href

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.abstract = abstract
            existing.pdf_url = pdf_url
            existing.html_url = html_url
            existing.primary_category = primary
            if published:
                existing.published_at = published
        else:
            db.add(
                Paper(
                    external_id=ext_id,
                    title=title,
                    abstract=abstract,
                    pdf_url=pdf_url,
                    html_url=html_url,
                    source="arxiv",
                    primary_category=primary,
                    published_at=published,
                )
            )
            count += 1
    db.commit()
    return count


def _parse_rss_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    if getattr(entry, "published", None):
        try:
            return parsedate_to_datetime(entry.published)
        except (TypeError, ValueError):
            pass
    return None


def fetch_and_upsert_rss(db: Session, feed_url: str) -> int:
    parsed = feedparser.parse(feed_url)
    count = 0
    for entry in parsed.entries:
        link = entry.get("link") or entry.get("id")
        if not link:
            continue
        ext_id = f"rss:{hashlib.md5(link.encode()).hexdigest()}"
        title = (entry.get("title") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        published = _parse_rss_date(entry)
        source = f"rss:{urlparse(feed_url).netloc or 'feed'}"

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title or existing.title
            existing.abstract = summary or existing.abstract
            existing.html_url = link
            if published:
                existing.published_at = published
        else:
            db.add(
                Paper(
                    external_id=ext_id,
                    title=title or "(no title)",
                    abstract=summary,
                    pdf_url=None,
                    html_url=link,
                    source=source,
                    primary_category=None,
                    published_at=published,
                )
            )
            count += 1
    db.commit()
    return count


def collect_subscription_rss_urls(db: Session) -> list[str]:
    """合并所有用户已启用期刊：预设 RSS + 手动填写的 rss URL，去重。"""
    seen: set[str] = set()
    out: list[str] = []
    for row in db.scalars(select(UserProfile)):
        try:
            arr = json.loads(row.subscription_journals_json or "[]")
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        for item in arr:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            custom = (item.get("rss") or "").strip()
            if custom.startswith(("http://", "https://")):
                if custom not in seen:
                    seen.add(custom)
                    out.append(custom)
                continue
            jid = item.get("id")
            if not jid or not isinstance(jid, str):
                continue
            preset = JOURNAL_PRESETS.get(jid)
            if not preset or not preset.rss:
                continue
            if preset.rss not in seen:
                seen.add(preset.rss)
                out.append(preset.rss)
    return out


def collect_subscription_openalex_source_ids(db: Session) -> list[str]:
    """所有用户已启用会议：预设里的 OpenAlex Source + 手动填写的 openalex_source_id。"""
    seen: set[str] = set()
    out: list[str] = []
    for row in db.scalars(select(UserProfile)):
        try:
            arr = json.loads(row.subscription_conferences_json or "[]")
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        for item in arr:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            raw_oid = (item.get("openalex_source_id") or "").strip()
            if raw_oid:
                oid = normalize_openalex_source_id(raw_oid)
                if oid and oid not in seen:
                    seen.add(oid)
                    out.append(oid)
                continue
            cid = (item.get("id") or "").strip()
            preset = CONFERENCE_PRESETS.get(cid)
            if not preset:
                continue
            pid = getattr(preset, "openalex_source_id", None)
            if pid and str(pid).strip() and str(pid) not in seen:
                seen.add(str(pid).strip())
                out.append(str(pid).strip())
    return out


def run_all_ingestion(db: Session) -> dict[str, int]:
    out: dict[str, int] = {"arxiv_new": fetch_and_upsert_arxiv(db)}
    for raw in settings.rss_feeds.split(","):
        u = raw.strip()
        if u:
            key = f"rss_new:{u[:30]}"
            out[key] = fetch_and_upsert_rss(db, u)
    for sub_url in collect_subscription_rss_urls(db):
        key = f"rss_sub:{sub_url[:40]}"
        out[key] = fetch_and_upsert_rss(db, sub_url)
    out["openalex_new"] = fetch_and_upsert_openalex(db)
    out["openalex_conference_new"] = fetch_and_upsert_openalex_conference_works(db)
    src_ids = collect_subscription_openalex_source_ids(db)
    out["openalex_subscription_sources"] = fetch_and_upsert_openalex_for_source_ids(db, src_ids)
    out["arxiv_citations_updated"] = enrich_arxiv_citations(db)
    return out


def run_ingestion_standalone() -> None:
    """定时任务与「保存订阅」后台任务共用。"""
    db = SessionLocal()
    try:
        out = run_all_ingestion(db)
        logger.info("ingestion %s", out)
    except Exception:
        logger.exception("ingestion failed")
    finally:
        db.close()
