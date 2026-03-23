"""OpenAlex ingestion and optional arXiv citation enrichment."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Paper
from app.services.author_format import openalex_authors_from_work

logger = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"


def _openalex_base_params() -> dict[str, str]:
    """mailto 必填礼貌参数；api_key 可选，官方建议规模化使用时携带。"""
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"
    out: dict[str, str] = {"mailto": mailto}
    key = (settings.openalex_api_key or "").strip()
    if key:
        out["api_key"] = key
    return out


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


def fetch_abstract_by_doi(doi: str) -> str:
    """
    只读：用 DOI 解析 OpenAlex Work，取 abstract_inverted_index 拼成摘要。
    不依赖 openalex_enabled（与抓取任务开关分离）。
    """
    doi = (doi or "").strip()
    if not doi.startswith("10.") or "/" not in doi:
        return ""
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"
    doi_url = f"https://doi.org/{doi}"
    params = _openalex_base_params()
    headers = {"User-Agent": f"LiteratureRadar/0.1 (mailto:{mailto})"}
    api_path = quote(doi_url, safe="")
    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            r = client.get(f"{OPENALEX_WORKS}/{api_path}", params=params)
        if r.status_code != 200:
            return ""
        w = r.json()
    except Exception:
        return ""
    if not isinstance(w, dict):
        return ""
    return _reconstruct_abstract(w.get("abstract_inverted_index")).strip()


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
        parts.append(f"primary_location.source.id:{_normalize_openalex_source_filter_value(vid)}")
    extra = settings.openalex_filter_extra.strip()
    if extra:
        parts.append(extra)
    return ",".join(parts)


def _normalize_openalex_source_filter_value(raw: str) -> str:
    """OpenAlex filter 中 source.id 可用短码 S123 或完整 URL。"""
    s = raw.strip()
    if not s:
        return s
    if s.startswith("http"):
        return s.rstrip("/")
    if re.match(r"^S\d+$", s, re.I):
        return f"https://openalex.org/{s}"
    if s.isdigit():
        return f"https://openalex.org/S{s}"
    return s


def normalize_openalex_source_id(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if s.startswith("http"):
        tail = s.rstrip("/").rsplit("/", 1)[-1]
        return tail if tail.startswith("S") else None
    if re.match(r"^S\d+$", s, re.I):
        return s.upper() if s[0] == "s" else s
    if s.isdigit():
        return f"S{s}"
    return None


def _upsert_openalex_works_batch(db: Session, results: list) -> int:
    """将 OpenAlex works 列表写入 papers，返回新增条数。"""
    count = 0
    for w in results:
        if not isinstance(w, dict):
            continue
        wid = _openalex_short_id(str(w.get("id") or ""))
        if not wid or not wid.startswith("W"):
            continue
        ext_id = f"openalex:{wid}"
        title = (w.get("title") or w.get("display_name") or "").strip() or "(no title)"
        # OpenAlex 仅提供 abstract_inverted_index；不少出版社（含部分 Nature 子刊）在索引中无摘要
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

        authors_text = openalex_authors_from_work(w)

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.abstract = abstract
            if authors_text:
                existing.authors_text = authors_text
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
                    authors_text=authors_text,
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


def _openalex_fetch_results(filter_str: str) -> list:
    if not settings.openalex_enabled:
        return []
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"
    params = {
        "filter": filter_str,
        "per_page": min(max(settings.openalex_per_page, 1), 200),
        "sort": "publication_date:desc",
        **_openalex_base_params(),
    }
    headers = {"User-Agent": f"LiteratureRadar/0.1 (mailto:{mailto})"}
    with httpx.Client(timeout=90.0, headers=headers) as client:
        r = client.get(OPENALEX_WORKS, params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("results") or []


def fetch_and_upsert_openalex(db: Session) -> int:
    if not settings.openalex_enabled:
        return 0
    results = _openalex_fetch_results(_build_openalex_filter())
    return _upsert_openalex_works_batch(db, results)


def fetch_and_upsert_openalex_conference_works(db: Session) -> int:
    """按「来源类型为会议 / proceedings」拉一批论文，填充「会议」频道（需开启 OpenAlex）。"""
    if not settings.openalex_enabled or not settings.openalex_fetch_conference_works:
        return 0
    d = date.today() - timedelta(days=settings.openalex_lookback_days)
    base = [
        "type:article",
        f"from_publication_date:{d.isoformat()}",
        "is_paratext:false",
    ]
    # OpenAlex 中部分 proceedings 的 source.type 为 proceedings 而非 conference，分两路拉取并去重
    type_filters = (
        "primary_location.source.type:conference",
        "primary_location.source.type:proceedings",
    )
    seen_wid: set[str] = set()
    merged: list = []
    for tf in type_filters:
        filt = ",".join([*base, tf])
        try:
            chunk = _openalex_fetch_results(filt)
        except Exception:
            logger.warning("openalex conference batch failed filter=%s", tf, exc_info=True)
            continue
        for w in chunk:
            if not isinstance(w, dict):
                continue
            wid = _openalex_short_id(str(w.get("id") or ""))
            if not wid or wid in seen_wid:
                continue
            seen_wid.add(wid)
            merged.append(w)
    if not merged:
        return 0
    try:
        return _upsert_openalex_works_batch(db, merged)
    except Exception:
        logger.warning("openalex conference upsert failed", exc_info=True)
        return 0


def fetch_and_upsert_openalex_for_source_ids(db: Session, source_ids: list[str]) -> int:
    """按用户订阅的 OpenAlex Source（会议/ proceedings）分别抓取。"""
    if not settings.openalex_enabled or not source_ids:
        return 0
    seen: set[str] = set()
    total = 0
    d = date.today() - timedelta(days=settings.openalex_lookback_days)
    per = min(max(settings.openalex_subscription_per_source, 1), 200)
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"
    base_q = _openalex_base_params()
    headers = {"User-Agent": f"LiteratureRadar/0.1 (mailto:{mailto})"}
    for raw in source_ids:
        sid = normalize_openalex_source_id(raw)
        if not sid or sid in seen:
            continue
        seen.add(sid)
        fv = _normalize_openalex_source_filter_value(sid)
        filt = ",".join(
            [
                "type:article",
                f"from_publication_date:{d.isoformat()}",
                "is_paratext:false",
                f"primary_location.source.id:{fv}",
            ]
        )
        params = {
            "filter": filt,
            "per_page": per,
            "sort": "publication_date:desc",
            **base_q,
        }
        try:
            with httpx.Client(timeout=90.0, headers=headers) as client:
                r = client.get(OPENALEX_WORKS, params=params)
                r.raise_for_status()
                data = r.json()
            results = data.get("results") or []
            total += _upsert_openalex_works_batch(db, results)
        except Exception:
            logger.warning("openalex subscription source fetch failed id=%s", sid, exc_info=True)
    return total


def _arxiv_abs_url(external_id: str) -> str | None:
    if not external_id.startswith("arxiv:"):
        return None
    tail = external_id[6:].strip()
    if not tail:
        return None
    return f"https://arxiv.org/abs/{tail}"


def enrich_arxiv_citations(db: Session) -> int:
    if not settings.openalex_enabled or not settings.openalex_enrich_arxiv_citations:
        return 0
    mailto = settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"
    base_q = _openalex_base_params()
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
                r = client.get(f"{OPENALEX_WORKS}/{api_path}", params=base_q)
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
