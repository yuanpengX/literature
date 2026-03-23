from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import FeedResponse
from app.services.recommend import load_candidate_papers, papers_to_feed_items
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

    papers = load_candidate_papers(db, limit=800, channel=ch)
    ordered = papers_to_feed_items(papers, user, sort)
    page = ordered[offset : offset + limit]
    next_offset = offset + limit
    next_cursor = str(next_offset) if next_offset < len(ordered) else None

    return FeedResponse(items=page, next_cursor=next_cursor)
