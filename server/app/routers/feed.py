from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import FeedResponse
from app.services.feed_blurbs import generate_missing_blurbs_background, merge_blurbs_into_feed_items
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
    background_tasks: BackgroundTasks,
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
    page = ordered[offset : offset + limit]
    merge_blurbs_into_feed_items(db, user_id, page)
    background_tasks.add_task(
        generate_missing_blurbs_background,
        user_id,
        [p.id for p in page],
    )
    next_offset = offset + limit
    next_cursor = str(next_offset) if next_offset < len(ordered) else None

    u_llm = db.get(UserProfile, user_id)
    blurbs_llm_ready = bool(
        u_llm
        and (u_llm.llm_api_key or "").strip()
        and (u_llm.llm_base_url or "").strip()
        and (u_llm.llm_model or "").strip()
    )

    return FeedResponse(
        items=page,
        next_cursor=next_cursor,
        blurbs_llm_ready=blurbs_llm_ready,
    )
