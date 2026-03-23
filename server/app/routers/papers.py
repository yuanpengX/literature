from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import Paper
from app.schemas import PaperOut
from app.services.recommend import read_value_stars_for_isolated_paper
from app.services.text_plain import strip_html_to_plain

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    stmt = select(Paper).options(joinedload(Paper.stats)).where(Paper.id == paper_id)
    p = db.execute(stmt).unique().scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found")
    hs = p.stats.hot_score if p.stats is not None else 0.0
    return PaperOut(
        id=p.id,
        external_id=p.external_id,
        title=p.title,
        abstract=strip_html_to_plain(p.abstract),
        authors_text=(p.authors_text or "").strip(),
        pdf_url=p.pdf_url,
        html_url=p.html_url,
        source=p.source,
        primary_category=p.primary_category,
        published_at=p.published_at,
        citation_count=p.citation_count,
        hot_score=hs,
        rank_reason=None,
        rank_tags=[],
        feed_blurb="",
        read_value_stars=read_value_stars_for_isolated_paper(hs),
    )
