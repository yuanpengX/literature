"""OpenAlex ingestion and optional arXiv citation enrichment."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Paper

logger = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inv.items():
        if not isinstance(idxs, list):
            continue
        for pos in idxs:
            if isinstance(pos, int):
                positions[pos] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))


def _openalex_short_id(work_url: str) -> str:
    if not work_url:
        return ""
    return work_url.rstrip("/").rsplit("/", 1)[-1]


def _parse_publication_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _build_openalex_filter() -> str:
    d = date.today() - timedelta(days=settings.openalex_lookback_days)
    parts = [
        "type:article",
        f"from_publication_date:{d.isoformat()}",
        "is_paratext:false",
    ]
    vid = settings.openalex_venue_source_id.strip()
    if vid:
        parts.append(f"primary_location.source.id:{vid}")
    extra = settings.openalex_filter_extra.strip()
    if extra:
        parts.append(extra)
    return ",".join(parts)


def fetch_and_upsert_openalex(db: Session) -> int:
    if not settings.openalex_enabled:
        return 0
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "dev@example.com"
    params = {
        "filter": _build_openalex_filter(),
        "per_page": min(max(settings.openalex_per_page, 1), 200),
        "sort": "publication_date:desc",
        "mailto": mailto,
    }
    headers = {"User-Agent": f"LiteratureRadar/0.1 (mailto:{mailto})"}
    with httpx.Client(timeout=90.0, headers=headers) as client:
        r = client.get(OPENALEX_WORKS, params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("results") or []
    count = 0
    for w in results:
        if not isinstance(w, dict):
            continue
        wid = _openalex_short_id(str(w.get("id") or ""))
        if not wid or not wid.startswith("W"):
            continue
        ext_id = f"openalex:{wid}"
        title = (w.get("title") or w.get("display_name") or "").strip() or "(no title)"
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
        cited = int(w.get("cited_by_count") or 0)
        published = _parse_publication_date(w.get("publication_date"))

        pl = w.get("primary_location") or {}
        html_url = pl.get("landing_page_url")
        pdf_url = pl.get("pdf_url")
        oa = w.get("open_access") or {}
        if not pdf_url:
            pdf_url = oa.get("oa_url")
        src = pl.get("source") or {}
        venue = (src.get("display_name") or pl.get("raw_source_name") or "") or None
        primary = (venue[:128] if venue else None)
        src_type = str(src.get("type") or "").lower().replace(" ", "")
        if src_type == "journal":
            paper_source = "openalex:journal"
        elif src_type in ("conference", "proceedings", "conferenceproceedings"):
            paper_source = "openalex:conference"
        else:
            paper_source = "openalex"

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.abstract = abstract
            existing.pdf_url = pdf_url
            existing.html_url = html_url
            existing.primary_category = primary
            existing.source = paper_source
            existing.citation_count = cited
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
                    source=paper_source,
                    primary_category=primary,
                    published_at=published,
                    citation_count=cited,
                )
            )
            count += 1
    db.commit()
    return count


def _arxiv_abs_url(external_id: str) -> str | None:
    # external_id like "arxiv:2301.12345" or legacy "arxiv:cs/0112017"
    if not external_id.startswith("arxiv:"):
        return None
    tail = external_id[6:].strip()
    if not tail:
        return None
    return f"https://arxiv.org/abs/{tail}"


def enrich_arxiv_citations(db: Session) -> int:
    if not settings.openalex_enabled or not settings.openalex_enrich_arxiv_citations:
        return 0
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "dev@example.com"
    headers = {"User-Agent": f"LiteratureRadar/0.1 (mailto:{mailto})"}
    limit = min(max(settings.openalex_enrich_per_run, 1), 100)
    pool = min(max(settings.openalex_enrich_pool, limit), 500)
    stmt = (
        select(Paper)
        .where(
            Paper.external_id.like("arxiv:%"),
            Paper.citation_synced_at.is_(None),
        )
        .order_by(Paper.ingested_at.desc())
        .limit(pool)
    )
    rows = list(db.scalars(stmt).all())
    updated = 0
    with httpx.Client(timeout=45.0, headers=headers) as client:
        for p in rows:
            if updated >= limit:
                break
            abs_url = _arxiv_abs_url(p.external_id)
            if not abs_url:
                continue
            api_path = quote(abs_url, safe="")
            try:
                r = client.get(f"{OPENALEX_WORKS}/{api_path}", params={"mailto": mailto})
                if r.status_code == 404:
                    p.citation_count = 0
                    p.citation_synced_at = datetime.now(timezone.utc)
                    updated += 1
                    continue
                if r.status_code != 200:
                    continue
                w = r.json()
                if not isinstance(w, dict) or w.get("title") is None:
                    continue
                cited = int(w.get("cited_by_count") or 0)
                p.citation_count = cited
                p.citation_synced_at = datetime.now(timezone.utc)
                updated += 1
            except Exception:
                logger.debug("openalex enrich failed for %s", p.external_id, exc_info=True)
    if updated:
        db.commit()
    return updated
