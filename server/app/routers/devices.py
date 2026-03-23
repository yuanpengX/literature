from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import current_user_id, get_db
from app.models import FcmToken
from app.schemas import FcmTokenIn

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/fcm-token")
def post_fcm_token(
    user_id: Annotated[str, Depends(current_user_id)],
    body: FcmTokenIn,
    db: Session = Depends(get_db),
):
    row = db.get(FcmToken, user_id)
    if row is None:
        db.add(FcmToken(user_id=user_id, token=body.token))
    else:
        row.token = body.token
    db.commit()
    return {"ok": True, "user_id": user_id}
