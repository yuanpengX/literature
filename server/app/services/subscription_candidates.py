"""订阅驱动的候选池：合并频道 + 按关键词/期刊/会议预筛（Feed 与每日精选共用）。"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.catalog.presets import CONFERENCE_PRESETS, JOURNAL_PRESETS, user_subscription_keywords_list
from app.models import Paper, UserProfile
from app.services.recommend import load_candidate_papers


def merge_subscription_candidate_papers(
    db: Session,
    *,
    max_total: int,
    per_channel_limit: int,
) -> list[Paper]:
    """与每日精选相同：合并 arxiv / journal / conference 候选并去重。"""
    seen: set[int] = set()
    out: list[Paper] = []
    for ch in ("arxiv", "journal", "conference"):
        for p in load_candidate_papers(db, limit=per_channel_limit, channel=ch):
            if p.id in seen:
                continue
            seen.add(p.id)
            out.append(p)
            if len(out) >= max_total:
                return out
    return out


def paper_matches_feed_channel(p: Paper, channel: str | None) -> bool:
    """与客户端频道 Tab 一致。"""
    if not channel:
        return True
    ch = channel.strip().lower()
    s = p.source or ""
    if ch == "arxiv":
        return s == "arxiv"
    if ch == "journal":
        return s == "openalex" or s.startswith("openalex:journal") or s.startswith("rss:")
    if ch == "conference":
        return s.startswith("openalex:conference")
    return True


def _enabled_journal_netlocs(subscription_journals_json: str) -> set[str]:
    out: set[str] = set()
    try:
        arr = json.loads(subscription_journals_json or "[]")
    except json.JSONDecodeError:
        return out
    if not isinstance(arr, list):
        return out
    for item in arr:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        custom = (item.get("rss") or "").strip()
        if custom.startswith(("http://", "https://")):
            host = urlparse(custom).netloc or ""
            if host:
                out.add(host.lower())
            continue
        jid = item.get("id")
        if not jid or not isinstance(jid, str):
            continue
        preset = JOURNAL_PRESETS.get(jid)
        if preset and preset.rss:
            host = urlparse(preset.rss).netloc or ""
            if host:
                out.add(host.lower())
    return out


def _conference_match_needles(subscription_conferences_json: str) -> list[str]:
    """用于与 Paper.primary_category（venue 名）子串匹配。"""
    needles: list[str] = []
    try:
        arr = json.loads(subscription_conferences_json or "[]")
    except json.JSONDecodeError:
        return needles
    if not isinstance(arr, list):
        return needles
    for item in arr:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        cid = (item.get("id") or "").strip()
        if cid:
            preset = CONFERENCE_PRESETS.get(cid)
            if preset:
                for part in (preset.name, preset.abbr, preset.note or ""):
                    t = (part or "").strip()
                    if len(t) >= 2:
                        needles.append(t.lower())
        name = (item.get("name") or "").strip()
        if name and len(name) >= 2:
            needles.append(name.lower())
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for n in needles:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def user_has_enabled_subscription(user: UserProfile) -> bool:
    if user_subscription_keywords_list(user):
        return True
    if _enabled_journal_netlocs(user.subscription_journals_json or "[]"):
        return True
    if _conference_match_needles(user.subscription_conferences_json or "[]"):
        return True
    return False


def _keyword_hit(p: Paper, keywords: list[str]) -> bool:
    if not keywords:
        return False
    blob = f"{p.title} {p.abstract}".lower()
    return any(k.lower() in blob for k in keywords)


def _journal_hit(p: Paper, netlocs: set[str]) -> bool:
    if not netlocs:
        return False
    src = (p.source or "").lower()
    if not src.startswith("rss:"):
        return False
    host = src[4:].split("/")[0].strip().lower()
    return host in netlocs


def _conference_hit(p: Paper, needles: list[str]) -> bool:
    if not needles:
        return False
    src = (p.source or "").lower()
    if not src.startswith("openalex:conference"):
        return False
    cat = (p.primary_category or "").lower()
    if not cat:
        return False
    return any(n in cat for n in needles if n)


def filter_papers_by_user_subscriptions(
    papers: list[Paper],
    user: UserProfile | None,
    *,
    strict: bool,
) -> list[Paper]:
    """
    (关键词命中) OR (期刊 RSS netloc) OR (会议 venue 子串)。
    无启用订阅时：strict=True 返回 []；strict=False 返回原列表。
    """
    u = user or UserProfile(user_id="_", keywords="", interest_blob="{}")
    if not user_has_enabled_subscription(u):
        if strict:
            return []
        return papers

    kws = user_subscription_keywords_list(u)
    netlocs = _enabled_journal_netlocs(u.subscription_journals_json or "[]")
    conf_needles = _conference_match_needles(u.subscription_conferences_json or "[]")

    out: list[Paper] = []
    for p in papers:
        if _keyword_hit(p, kws) or _journal_hit(p, netlocs) or _conference_hit(p, conf_needles):
            out.append(p)
    return out
