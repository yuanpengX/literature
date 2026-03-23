import hashlib
import logging
import re
import threading
import time
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
from app.services.author_format import format_author_line
from app.services.text_plain import (
    _is_metadata_only_plain,
    strip_html_to_plain,
    strip_rss_boilerplate_html,
)
from app.services.openalex import (
    enrich_arxiv_citations,
    fetch_and_upsert_openalex,
    fetch_and_upsert_openalex_conference_works,
    fetch_and_upsert_openalex_for_source_ids,
    normalize_openalex_source_id,
)

logger = logging.getLogger(__name__)

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}

_arxiv_user_lock = threading.Lock()
_arxiv_user_last_mono: dict[str, float] = {}


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    m = re.search(r"arxiv\.org/abs/([^?#]+)", entry_id, re.I)
    if m:
        return f"arxiv:{m.group(1)}"
    return f"arxiv:{entry_id[-32:]}"


def _upsert_arxiv_atom_entries(db: Session, root: ET.Element) -> int:
    """解析 arXiv Atom API 根节点并写入 papers，返回新增行数。"""
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

        author_names: list[str] = []
        for auth_el in entry.findall("atom:author", ARXIV_NS):
            ne = auth_el.find("atom:name", ARXIV_NS)
            if ne is not None and (ne.text or "").strip():
                author_names.append(" ".join((ne.text or "").split()))
        authors_text = format_author_line(author_names)

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.abstract = abstract
            existing.authors_text = authors_text or existing.authors_text
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
                    authors_text=authors_text,
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


def fetch_and_upsert_arxiv_search(db: Session, search_query: str, max_results: int) -> int:
    """按任意 arXiv API search_query 拉取并 upsert；返回新增条数。"""
    q = (search_query or "").strip()
    if not q:
        return 0
    cap = min(max(1, max_results), 2000)
    params = {
        "search_query": q,
        "sortBy": "submittedDate",
        "max_results": cap,
    }
    url = "https://export.arxiv.org/api/query"
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    return _upsert_arxiv_atom_entries(db, root)


def fetch_and_upsert_arxiv(db: Session) -> int:
    """定时任务：全局 categories 查询（settings.arxiv_query）。"""
    return fetch_and_upsert_arxiv_search(db, settings.arxiv_query, settings.arxiv_max_results)


def _arxiv_normalize_keyword_phrase(raw: str) -> str:
    s = (raw or "").strip().replace('"', " ").replace("\\", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) < 2:
        return ""
    return s[:240]


def build_arxiv_or_query_from_keywords(keywords: list[str]) -> str | None:
    """多条订阅关键词 OR；每条用 all:\"phrase\" 在标题+摘要中检索。"""
    max_terms = min(max(settings.arxiv_keyword_max_terms, 1), 20)
    clauses: list[str] = []
    for kw in keywords[:max_terms]:
        phrase = _arxiv_normalize_keyword_phrase(kw)
        if not phrase:
            continue
        clauses.append(f'all:"{phrase}"')
    if not clauses:
        return None
    return " OR ".join(clauses)


def maybe_fetch_arxiv_for_user_keywords(db: Session, user_id: str, keywords: list[str]) -> None:
    """
    用户拉取 arXiv 频道时调用：按关键词查询 arXiv API 并入库（带进程内节流，避免触达 polite 限流）。
    """
    if not keywords or not user_id or user_id == "anonymous":
        return
    q = build_arxiv_or_query_from_keywords(keywords)
    if not q:
        return
    interval = max(30.0, float(settings.arxiv_user_refresh_seconds))
    now = time.monotonic()
    with _arxiv_user_lock:
        last = _arxiv_user_last_mono.get(user_id, 0.0)
        if now - last < interval:
            return
    try:
        n = fetch_and_upsert_arxiv_search(
            db,
            q,
            settings.arxiv_keyword_max_results,
        )
        with _arxiv_user_lock:
            _arxiv_user_last_mono[user_id] = time.monotonic()
        logger.info("arxiv keyword fetch user=%s new_rows=%s", user_id[:24], n)
    except Exception:
        logger.exception("arxiv keyword fetch failed user=%s", user_id[:24])


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


_RSS_TITLE_NOISE_SUBSTRINGS: tuple[str, ...] = (
    "issue publication",
    "editorial masthead",
    "masthead",
    "table of contents",
    "in this issue",
    "cover image",
    "front cover",
    "front matter",
    "announcement",
)

_RSS_TITLE_SHORT_GENERIC_EXACT: frozenset[str] = frozenset(
    {
        "toc",
        "contents",
        "cover",
        "masthead",
        "editorial",
        "issue contents",
        "this issue",
        "in brief",
        "highlights",
        "foreword",
        "preface",
    }
)


def _rss_entry_skip_noise(title: str) -> bool:
    """期刊 RSS 目录页等非论文条目：标题噪声则跳过。"""
    t = (title or "").strip()
    if not t:
        return True
    low = t.casefold()
    for s in _RSS_TITLE_NOISE_SUBSTRINGS:
        if s in low:
            return True
    if len(t) <= 3:
        return True
    if low in _RSS_TITLE_SHORT_GENERIC_EXACT:
        return True
    if len(t) <= 18 and " " not in t and low in _RSS_TITLE_SHORT_GENERIC_EXACT:
        return True
    return False


def _rss_content_values(entry) -> list[str]:
    raw = getattr(entry, "content", None)
    if not raw or not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        val = None
        if hasattr(item, "value"):
            val = getattr(item, "value", None)
        elif isinstance(item, dict):
            val = item.get("value")
        if val is not None and str(val).strip():
            out.append(str(val))
    return out


def _rss_summary_raw_candidates(entry) -> list[str]:
    """feedparser 各字段原始 HTML，顺序：summary / description / content[*]。"""
    out: list[str] = []
    for key in ("summary", "description"):
        v = entry.get(key)
        if v:
            out.append(str(v))
    out.extend(_rss_content_values(entry))
    return out


def _rss_best_summary(entry) -> str:
    """取第一条非「纯卷期/出版元信息」的摘要；ACS 等仅 TOC 行时返回空字符串。"""
    for raw in _rss_summary_raw_candidates(entry):
        cleaned = strip_rss_boilerplate_html(str(raw) if raw else "")
        plain = strip_html_to_plain(cleaned)
        if plain and not _is_metadata_only_plain(plain):
            return plain
    return ""


def fetch_and_upsert_rss(db: Session, feed_url: str) -> int:
    parsed = feedparser.parse(feed_url)
    count = 0
    for entry in parsed.entries:
        link = entry.get("link") or entry.get("id")
        if not link:
            continue
        ext_id = f"rss:{hashlib.md5(link.encode()).hexdigest()}"
        title = strip_html_to_plain(entry.get("title") or "")
        if _rss_entry_skip_noise(title):
            continue
        summary = _rss_best_summary(entry)
        published = _parse_rss_date(entry)
        source = f"rss:{urlparse(feed_url).netloc or 'feed'}"
        rss_authors: list[str] = []
        if getattr(entry, "author", None):
            rss_authors.append(str(entry.author).strip())
        if getattr(entry, "authors", None):
            for a in entry.authors:
                if hasattr(a, "name") and a.name:
                    rss_authors.append(str(a.name).strip())
                elif isinstance(a, str):
                    rss_authors.append(a.strip())
        authors_text = format_author_line(rss_authors, max_show=5)

        existing = db.execute(select(Paper).where(Paper.external_id == ext_id)).scalar_one_or_none()
        if existing:
            existing.title = title or existing.title
            existing.abstract = summary or existing.abstract
            if authors_text:
                existing.authors_text = authors_text
            existing.html_url = link
            if published:
                existing.published_at = published
        else:
            db.add(
                Paper(
                    external_id=ext_id,
                    title=title or "(no title)",
                    abstract=summary,
                    authors_text=authors_text,
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
