from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import Paper
from app.schemas import PaperOut, SearchResponse
from app.services.recommend import papers_to_feed_items

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search_papers(
    db: Session = Depends(get_db),
    q: Annotated[str, Query(min_length=1)] = "",
    limit: int = Query(30, ge=1, le=100),
):
    term = f"%{q.strip()}%"
    stmt = (
        select(Paper)
        .options(joinedload(Paper.stats))
        .where(or_(Paper.title.ilike(term), Paper.abstract.ilike(term)))
        .order_by(Paper.published_at.desc().nulls_last(), Paper.id.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).unique().all())
    items = papers_to_feed_items(rows, None, sort="recent")
    return SearchResponse(items=items)
