import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import PreferencesUpdate, UserLlmCredentials
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users/me", tags=["users"])


@router.put("/preferences")
def put_preferences(
    user_id: Annotated[str, Depends(current_user_id)],
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
):
    parts = [p.strip() for p in body.keywords.split(",") if p.strip()]
    kw_json = json.dumps([{"text": p, "enabled": True} for p in parts], ensure_ascii=False)
    u = db.get(UserProfile, user_id)
    if u is None:
        u = UserProfile(
            user_id=user_id,
            keywords=body.keywords,
            subscription_keywords_json=kw_json,
        )
        db.add(u)
    else:
        u.keywords = body.keywords
        u.subscription_keywords_json = kw_json
    db.commit()
    return {"ok": True}


@router.put("/llm")
def put_llm_credentials(
    user_id: Annotated[str, Depends(current_user_id)],
    body: UserLlmCredentials,
    db: Session = Depends(get_db),
):
    """将 LLM 配置保存到服务器，供每日精选定时任务调用（请仅用于可信自建服务）。"""
    bu = body.base_url.strip()
    if not bu.lower().startswith("http"):
        raise HTTPException(status_code=400, detail="base_url 须为 http(s) 地址")
    u = db.get(UserProfile, user_id)
    if u is None:
        u = UserProfile(user_id=user_id)
        db.add(u)
    u.llm_base_url = bu
    u.llm_api_key = body.api_key.strip()
    u.llm_model = body.model.strip()
    db.commit()
    return {"ok": True}


@router.delete("/llm")
def delete_llm_credentials(
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
):
    u = db.get(UserProfile, user_id)
    if u is not None:
        u.llm_base_url = ""
        u.llm_api_key = ""
        u.llm_model = ""
        db.commit()
    return {"ok": True}
