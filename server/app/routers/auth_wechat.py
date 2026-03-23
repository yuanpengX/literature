"""微信小程序：code2Session + JWT，与 Android X-User-Id 并存。"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models import UserProfile
from app.schemas import WeChatLoginBody, WeChatLoginResponse
from app.services.jwt_tokens import issue_access_token
from app.services.user_defaults import default_subscription_fields

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

WECHAT_CODE2SESSION = "https://api.weixin.qq.com/sns/jscode2session"


@router.post("/auth/wechat/login", response_model=WeChatLoginResponse)
def wechat_miniprogram_login(
    body: WeChatLoginBody,
    db: Annotated[Session, Depends(get_db)],
):
    app_id = (settings.wechat_miniprogram_app_id or "").strip()
    secret = (settings.wechat_miniprogram_app_secret or "").strip()
    if not app_id or not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务端未配置微信小程序 AppID/AppSecret",
        )
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code 不能为空")

    params = {
        "appid": app_id,
        "secret": secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(WECHAT_CODE2SESSION, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("wechat code2session http error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法连接微信登录服务",
        ) from e

    if data.get("errcode"):
        err = data.get("errmsg") or str(data.get("errcode"))
        logger.info("wechat code2session err: %s", data)
        raise HTTPException(status_code=400, detail=f"微信登录失败: {err}")

    openid = (data.get("openid") or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="微信未返回 openid")

    user_id = f"wx:{openid}"
    u = db.get(UserProfile, user_id)
    if u is None:
        d = default_subscription_fields()
        u = UserProfile(
            user_id=user_id,
            keywords=d["keywords"],
            subscription_keywords_json=d["subscription_keywords_json"],
            subscription_journals_json=d["subscription_journals_json"],
            subscription_conferences_json=d["subscription_conferences_json"],
        )
        db.add(u)
        db.commit()

    try:
        token, expires_in = issue_access_token(user_id)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e

    return WeChatLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )
