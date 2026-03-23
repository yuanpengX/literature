from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import current_user_id, get_db
from app.schemas import AnalyticsBatchIn
from app.services.analytics import apply_event_batch

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def post_events(
    user_id: Annotated[str, Depends(current_user_id)],
    body: AnalyticsBatchIn,
    db: Session = Depends(get_db),
):
    if body.events:
        apply_event_batch(db, user_id, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
