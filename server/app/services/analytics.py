import json

from sqlalchemy.orm import Session

from app.models import AnalyticsEvent, Paper, PaperStat, UserProfile
from app.schemas import AnalyticsBatchIn
from app.services.tokenize import merge_interest_weights


def _ensure_stat(db: Session, paper_id: int) -> PaperStat:
    st = db.get(PaperStat, paper_id)
    if st is None:
        st = PaperStat(paper_id=paper_id, hot_score=0.0)
        db.add(st)
        db.flush()
    return st


def _ensure_user(db: Session, user_id: str) -> UserProfile:
    u = db.get(UserProfile, user_id)
    if u is None:
        u = UserProfile(user_id=user_id)
        db.add(u)
        db.flush()
    return u


def apply_event_batch(db: Session, user_id: str, batch: AnalyticsBatchIn) -> None:
    user = _ensure_user(db, user_id)
    for ev in batch.events:
        paper = db.get(Paper, ev.paper_id) if ev.paper_id is not None else None

        db.add(
            AnalyticsEvent(
                user_id=user_id,
                event_type=ev.event_type,
                paper_id=ev.paper_id,
                surface=ev.surface,
                position=ev.position,
                payload_json=json.dumps(ev.payload, ensure_ascii=False),
            )
        )

        if paper is None:
            continue

        st = _ensure_stat(db, paper.id)

        if ev.event_type == "feed_impression":
            st.hot_score += 0.05
            st.impression_count += 1
        elif ev.event_type == "paper_open":
            st.hot_score += 2.0
            st.click_count += 1
            user.interest_blob = merge_interest_weights(user.interest_blob, f"{paper.title} {paper.abstract}", 1.0)
        elif ev.event_type == "detail_leave":
            st.hot_score += 0.3
        elif ev.event_type == "save":
            st.hot_score += 4.0
            st.save_count += 1
            user.interest_blob = merge_interest_weights(user.interest_blob, f"{paper.title} {paper.abstract}", 1.5)
        elif ev.event_type == "unsave":
            st.hot_score = max(0.0, st.hot_score - 2.0)
            st.save_count = max(0, st.save_count - 1)
        elif ev.event_type == "open_pdf_inapp":
            st.hot_score += 1.5
            st.click_count += 1
        elif ev.event_type == "open_external_link":
            st.hot_score += 1.0
            st.click_count += 1

    db.commit()
