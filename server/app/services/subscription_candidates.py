"""订阅驱动的候选池：合并频道 + 按订阅关键词预筛（Feed 与每日精选共用）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.presets import user_subscription_keywords_list
from app.models import Paper, UserProfile
from app.services.recommend import load_candidate_papers
from app.services.text_plain import strip_html_to_plain


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


def _keyword_hit(p: Paper, keywords: list[str]) -> bool:
    if not keywords:
        return False
    blob = f"{p.title} {strip_html_to_plain(p.abstract)}".lower()
    return any(k.lower() in blob for k in keywords)


def filter_papers_by_user_subscriptions(
    papers: list[Paper],
    user: UserProfile | None,
    *,
    strict: bool,
) -> list[Paper]:
    """
    仅保留「标题或摘要」命中用户已启用订阅关键词的论文。
    未启用任何关键词时返回空列表（strict 参数保留兼容调用方，行为与关键词缺失一致）。
    期刊 / 会议订阅仍影响抓取与目录展示，但进入推荐列表须满足关键词命中。
    """
    _ = strict
    u = user or UserProfile(user_id="_", keywords="", interest_blob="{}")
    kws = user_subscription_keywords_list(u)
    if not kws:
        return []

    out: list[Paper] = []
    for p in papers:
        if _keyword_hit(p, kws):
            out.append(p)
    return out
