from typing import Annotated

from fastapi import Header, HTTPException, status

from app.database import SessionLocal
from app.services.jwt_tokens import decode_access_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    """
    优先 Authorization: Bearer <JWT>（小程序）；
    否则 X-User-Id（Android 等）；再否则 anonymous。
    若带了 Bearer 但 token 无效，返回 401。
    """
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw = parts[1].strip()
            if not raw:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="缺少 access_token",
                )
            uid = decode_access_token(raw)
            if uid:
                return uid
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录已失效，请重新进入小程序",
            )
    return (x_user_id or "anonymous").strip() or "anonymous"
