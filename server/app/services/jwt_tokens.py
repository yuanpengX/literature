from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def issue_access_token(user_id: str) -> tuple[str, int]:
    if not (settings.jwt_secret or "").strip():
        raise RuntimeError("JWT_SECRET 未配置")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=float(settings.jwt_expires_days))
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret.strip(), algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    expires_in = max(1, int((exp - now).total_seconds()))
    return token, expires_in


def decode_access_token(token: str) -> str | None:
    if not (settings.jwt_secret or "").strip():
        return None
    try:
        payload = jwt.decode(
            token.strip(),
            settings.jwt_secret.strip(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    if isinstance(sub, str) and sub.strip():
        return sub.strip()
    return None
