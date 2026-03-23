from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.catalog.presets import user_subscription_keywords_list
from app.config import settings
from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import FeedResponse
from app.services.feed_blurbs import collect_feed_items_with_blurbs
from app.services.ingest import (
    maybe_fetch_arxiv_for_user_keywords,
    maybe_fetch_openalex_journal_for_user_keywords,
)
from app.services.recommend import papers_to_feed_items
from app.services.subscription_candidates import (
    filter_papers_by_user_subscriptions,
    merge_subscription_candidate_papers,
    paper_matches_feed_channel,
)
from app.services.user_defaults import default_subscription_fields

router = APIRouter(prefix="/feed", tags=["feed"])

FeedSort = Literal["recommended", "recent", "hot", "for_you"]


@router.get("", response_model=FeedResponse)
def get_feed(
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
    cursor: str | None = Query(None, description="Offset string for pagination"),
    limit: int = Query(20, ge=1, le=100),
    sort: FeedSort = "recommended",
    channel: str | None = Query(
        None,
        description="arxiv | journal | conference；不传则不分频道（全部）",
    ),
):
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError:
            offset = 0

    raw = (channel or "").strip().lower()
    if not raw:
        ch = None
    elif raw in ("arxiv", "journal", "conference"):
        ch = raw
    else:
        raise HTTPException(status_code=400, detail="channel 须为 arxiv、journal 或 conference")

    user = db.get(UserProfile, user_id)
    if user is None and user_id != "anonymous":
        d = default_subscription_fields()
        user = UserProfile(
            user_id=user_id,
            keywords=d["keywords"],
            subscription_keywords_json=d["subscription_keywords_json"],
            subscription_journals_json=d["subscription_journals_json"],
            subscription_conferences_json=d["subscription_conferences_json"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if ch == "arxiv" and user_id != "anonymous" and user is not None:
        kws = user_subscription_keywords_list(user)
        if kws:
            maybe_fetch_arxiv_for_user_keywords(db, user_id, kws)

    if ch == "journal" and user_id != "anonymous" and user is not None:
        kws = user_subscription_keywords_list(user)
        if kws:
            maybe_fetch_openalex_journal_for_user_keywords(db, user_id, kws)

    merged = merge_subscription_candidate_papers(
        db,
        max_total=settings.feed_merge_max_total,
        per_channel_limit=settings.feed_merge_per_channel,
    )
    filtered = filter_papers_by_user_subscriptions(
        merged,
        user,
        strict=settings.feed_strict_subscription_filter,
    )
    papers = [p for p in filtered if paper_matches_feed_channel(p, ch)]
    ordered = papers_to_feed_items(papers, user, sort)

    blurbs_llm_ready = bool(
        user is not None
        and user_id != "anonymous"
        and (user.llm_api_key or "").strip()
        and (user.llm_base_url or "").strip()
        and (user.llm_model or "").strip()
    )

    if not blurbs_llm_ready:
        return FeedResponse(
            items=[],
            next_cursor=None,
            blurbs_llm_ready=False,
        )

    page, next_idx = collect_feed_items_with_blurbs(
        db,
        user_id,
        ordered,
        offset,
        limit,
        abstract_enrich_enabled=settings.abstract_enrich_enabled,
        max_scan_multiplier=settings.feed_llm_ensure_max_scan_multiplier,
    )
    next_cursor = str(next_idx) if next_idx < len(ordered) else None

    return FeedResponse(
        items=page,
        next_cursor=next_cursor,
        blurbs_llm_ready=True,
    )
