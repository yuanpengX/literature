from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.presets import user_subscription_keywords_list
from app.deps import current_user_id, get_db
from app.models import DailyPick, UserProfile
from app.schemas import DailyPicksResponse
from app.services.daily_picks import (
    _pick_date_str,
    generate_daily_pick_for_user,
    load_daily_pick_papers,
)

router = APIRouter(prefix="/daily-picks", tags=["daily-picks"])


def _server_llm_configured(u: UserProfile | None) -> bool:
    if u is None:
        return False
    return bool(
        u.llm_api_key.strip() and u.llm_base_url.strip() and u.llm_model.strip(),
    )


@router.get("/me", response_model=DailyPicksResponse)
def get_my_daily_picks(
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
    date: str | None = Query(None, description="YYYY-MM-DD，默认按服务器配置的时区「今日」"),
):
    d = (date or "").strip() or _pick_date_str()
    u = db.get(UserProfile, user_id)
    items, note, err = load_daily_pick_papers(db, user_id, d)
    kws = user_subscription_keywords_list(u) if u is not None else []
    return DailyPicksResponse(
        date=d,
        items=items,
        note=note,
        error=err,
        server_llm_configured=_server_llm_configured(u),
        subscription_keywords=kws,
    )


@router.post("/me/run", response_model=DailyPicksResponse)
def run_my_daily_pick_now(
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
):
    """立即为当前用户生成「今日」精选（覆盖当日已有结果）。需已配置服务端 LLM。"""
    u = db.get(UserProfile, user_id)
    if u is None or not _server_llm_configured(u):
        raise HTTPException(status_code=400, detail="请先在设置中同步 LLM 到服务器")
    pick_date = _pick_date_str()
    row = db.execute(
        select(DailyPick).where(DailyPick.user_id == user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    generate_daily_pick_for_user(db, u, pick_date)
    items, note, err = load_daily_pick_papers(db, user_id, pick_date)
    kws = user_subscription_keywords_list(u)
    return DailyPicksResponse(
        date=pick_date,
        items=items,
        note=note,
        error=err,
        server_llm_configured=True,
        subscription_keywords=kws,
    )
