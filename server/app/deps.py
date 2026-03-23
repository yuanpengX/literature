from typing import Annotated

from fastapi import Header

from app.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    return (x_user_id or "anonymous").strip() or "anonymous"
