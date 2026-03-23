"""论文摘要二次抓取：RSS/TOC 无正文摘要时，按 DOI 与落地页补全。"""

from __future__ import annotations

import html as html_mod
import logging
import re
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Paper
from app.services.openalex import fetch_abstract_by_doi
from app.services.text_plain import _is_metadata_only_plain, strip_html_to_plain

logger = logging.getLogger(__name__)

_DOI_IN_TEXT_RE = re.compile(r"(10\.\d{4,9}/[^\s?#)<\"]+)", re.I)


def _mailto_for_ua() -> str:
    return settings.openalex_mailto.replace("mailto:", "").strip() or "admin@cppteam.cn"


def doi_from_paper(p: Paper) -> str | None:
    for u in (p.html_url, p.pdf_url):
        if not u:
            continue
        m = _DOI_IN_TEXT_RE.search(u)
        if m:
            return m.group(1).rstrip(".,;)]>'\"")
    return None


def _clean_candidate_abstract(raw: str) -> str:
    t = strip_html_to_plain(raw)
    if len(t) > 8000:
        t = t[:8000]
    return t.strip()


def _acceptable_abstract(plain: str) -> bool:
    return bool(plain) and len(plain) >= 28 and not _is_metadata_only_plain(plain)


def fetch_abstract_crossref(doi: str) -> str:
    mailto = _mailto_for_ua()
    headers = {"User-Agent": f"LiteratureRadar/1.0 (mailto:{mailto})"}
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    try:
        with httpx.Client(timeout=settings.abstract_enrich_http_timeout, headers=headers) as client:
            r = client.get(url)
        if r.status_code != 200:
            return ""
        msg = r.json().get("message") or {}
        ab = msg.get("abstract")
    except Exception:
        return ""
    if isinstance(ab, str) and ab.strip():
        s = re.sub(r"<[^>]+>", " ", ab)
        return _clean_candidate_abstract(html_mod.unescape(s))
    if isinstance(ab, list):
        parts: list[str] = []
        for block in ab:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("p") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return _clean_candidate_abstract(" ".join(parts))
    return ""


def fetch_abstract_europepmc(doi: str) -> str:
    try:
        with httpx.Client(timeout=settings.abstract_enrich_http_timeout) as client:
            r = client.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={
                    "query": f"DOI:{doi}",
                    "format": "json",
                    "resultType": "core",
                    "pageSize": 5,
                },
            )
        if r.status_code != 200:
            return ""
        data = r.json()
        results = (data.get("resultList") or {}).get("result") or []
        for row in results:
            if not isinstance(row, dict):
                continue
            t = (row.get("abstractText") or row.get("abstract") or "").strip()
            if t:
                return _clean_candidate_abstract(t)
    except Exception:
        return ""
    return ""


def fetch_abstract_semanticscholar(doi: str) -> str:
    try:
        with httpx.Client(timeout=settings.abstract_enrich_http_timeout) as client:
            r = client.get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}",
                params={"fields": "abstract"},
            )
        if r.status_code != 200:
            return ""
        data = r.json()
        if not isinstance(data, dict):
            return ""
        return _clean_candidate_abstract(data.get("abstract") or "")
    except Exception:
        return ""


def fetch_abstract_landing_meta(url: str) -> str:
    if not url or not url.startswith("http"):
        return ""
    mailto = _mailto_for_ua()
    headers = {
        "User-Agent": f"Mozilla/5.0 (compatible; LiteratureRadar/1.0; +mailto:{mailto})",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(
            timeout=settings.abstract_enrich_http_timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            r = client.get(url)
        if r.status_code != 200 or len(r.text) < 400:
            return ""
        h = r.text
    except Exception:
        return ""
    for pat in (
        r'<meta\s+name="citation_abstract"\s+content="([^"]*)"',
        r'<meta\s+property="og:description"\s+content="([^"]*)"',
        r'<meta\s+name="description"\s+content="([^"]*)"',
    ):
        m = re.search(pat, h, re.I | re.DOTALL)
        if not m:
            continue
        raw = html_mod.unescape(m.group(1).replace("&quot;", '"').replace("&#x27;", "'"))
        plain = _clean_candidate_abstract(raw)
        if _acceptable_abstract(plain):
            return plain
    return ""


def try_fetch_abstract_for_paper(p: Paper) -> str:
    doi = doi_from_paper(p)
    chain: list[str] = []
    if doi:
        chain.append(fetch_abstract_by_doi(doi))
        chain.append(fetch_abstract_crossref(doi))
        chain.append(fetch_abstract_europepmc(doi))
        chain.append(fetch_abstract_semanticscholar(doi))
    if p.html_url:
        chain.append(fetch_abstract_landing_meta(p.html_url))
    for cand in chain:
        if _acceptable_abstract(cand):
            return cand
    return ""


def paper_needs_abstract_enrichment(p: Paper) -> bool:
    plain = strip_html_to_plain(p.abstract)
    return (not plain) or _is_metadata_only_plain(plain)


def enrich_papers_for_feed_ids(db: Session, paper_ids: list[int]) -> int:
    """就地更新 Paper.abstract 并 commit。返回成功写入条数。"""
    if not settings.abstract_enrich_enabled or not paper_ids:
        return 0
    cap = max(1, settings.feed_abstract_enrich_max_per_request)
    updated = 0
    for pid in paper_ids:
        if updated >= cap:
            break
        p = db.get(Paper, pid)
        if p is None or not paper_needs_abstract_enrichment(p):
            continue
        if not (p.html_url or p.pdf_url):
            continue
        text = try_fetch_abstract_for_paper(p)
        if not text:
            continue
        p.abstract = text
        updated += 1
    if updated:
        try:
            db.commit()
        except Exception:
            logger.exception("abstract enrich commit failed")
            db.rollback()
            return 0
    return updated


def refresh_feed_items_abstracts(db: Session, items: list) -> None:
    """PaperOut 列表：用数据库中最新 abstract 覆盖。"""
    if not items:
        return
    ids = [it.id for it in items]
    stmt = select(Paper).where(Paper.id.in_(ids))
    by_id = {row.id: row for row in db.scalars(stmt).all()}
    for i, it in enumerate(list(items)):
        row = by_id.get(it.id)
        if row is None:
            continue
        new_abst = strip_html_to_plain(row.abstract)
        if new_abst == (it.abstract or ""):
            continue
        items[i] = it.model_copy(update={"abstract": new_abst})
