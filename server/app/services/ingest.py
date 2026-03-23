import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Paper
from app.services.openalex import enrich_arxiv_citations, fetch_and_upsert_openalex


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


def run_all_ingestion(db: Session) -> dict[str, int]:
    out: dict[str, int] = {"arxiv_new": fetch_and_upsert_arxiv(db)}
    for raw in settings.rss_feeds.split(","):
        u = raw.strip()
        if u:
            key = f"rss_new:{u[:30]}"
            out[key] = fetch_and_upsert_rss(db, u)
    out["openalex_new"] = fetch_and_upsert_openalex(db)
    out["arxiv_citations_updated"] = enrich_arxiv_citations(db)
    return out
