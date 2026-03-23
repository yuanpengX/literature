from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import PreferencesUpdate
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users/me", tags=["users"])


@router.put("/preferences")
def put_preferences(
    user_id: Annotated[str, Depends(current_user_id)],
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
):
    u = db.get(UserProfile, user_id)
    if u is None:
        u = UserProfile(user_id=user_id, keywords=body.keywords)
        db.add(u)
    else:
        u.keywords = body.keywords
    db.commit()
    return {"ok": True}
