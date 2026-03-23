"""订阅配置：关键词、期刊（含 RSS 预设）、会议（元数据，供客户端展示与未来抓取扩展）。"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.catalog.presets import (
    CONFERENCE_PRESETS,
    JOURNAL_PRESETS,
    default_subscription_conferences,
    default_subscription_journals,
    default_subscription_keywords,
)
from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.services.ingest import run_ingestion_standalone
from app.services.user_defaults import default_subscription_tuple
from app.schemas import (
    ConferencePresetOut,
    JournalPresetOut,
    SubscriptionCatalogResponse,
    SubscriptionConferenceItem,
    SubscriptionJournalItem,
    SubscriptionKeywordItem,
    UserSubscriptionsPut,
    UserSubscriptionsResponse,
)

router = APIRouter(tags=["subscriptions"])


def _parse_keywords(json_str: str) -> list[SubscriptionKeywordItem]:
    try:
        arr = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[SubscriptionKeywordItem] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        t = (x.get("text") or "").strip()
        if not t:
            continue
        out.append(SubscriptionKeywordItem(text=t, enabled=bool(x.get("enabled", True))))
    return out


def _parse_journals(json_str: str) -> list[SubscriptionJournalItem]:
    try:
        arr = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[SubscriptionJournalItem] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        jid = (x.get("id") or "").strip()
        if not jid:
            continue
        nm = x.get("name")
        rs = x.get("rss")
        out.append(
            SubscriptionJournalItem(
                id=jid,
                enabled=bool(x.get("enabled", True)),
                name=str(nm).strip() if nm else None,
                rss=str(rs).strip() if rs else None,
            )
        )
    return out


def _parse_conferences(json_str: str) -> list[SubscriptionConferenceItem]:
    try:
        arr = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[SubscriptionConferenceItem] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        cid = (x.get("id") or "").strip()
        if not cid:
            continue
        nm = x.get("name")
        oid = x.get("openalex_source_id")
        out.append(
            SubscriptionConferenceItem(
                id=cid,
                enabled=bool(x.get("enabled", True)),
                name=str(nm).strip() if nm else None,
                openalex_source_id=str(oid).strip() if oid else None,
            )
        )
    return out


def _migrate_keywords_csv_to_json(u: UserProfile) -> bool:
    """若 JSON 为空但 keywords 有旧 CSV，则写入 subscription_keywords_json。返回是否修改。"""
    cur = _parse_keywords(u.subscription_keywords_json)
    if cur:
        return False
    csv = (u.keywords or "").strip()
    if not csv:
        return False
    parts = [p.strip() for p in csv.split(",") if p.strip()]
    u.subscription_keywords_json = json.dumps(
        [{"text": p, "enabled": True} for p in parts],
        ensure_ascii=False,
    )
    return True


def _default_profile_payload() -> tuple[str, str, str, str]:
    return default_subscription_tuple()


@router.get("/subscriptions/catalog", response_model=SubscriptionCatalogResponse)
def get_subscription_catalog():
    journals = [
        JournalPresetOut(
            id=p.id,
            name=p.name,
            abbr=p.abbr,
            issn=p.issn,
            rss=p.rss,
        )
        for p in sorted(JOURNAL_PRESETS.values(), key=lambda x: x.name)
    ]
    conferences = [
        ConferencePresetOut(
            id=p.id,
            name=p.name,
            abbr=p.abbr,
            note=p.note,
            openalex_source_id=p.openalex_source_id,
        )
        for p in sorted(CONFERENCE_PRESETS.values(), key=lambda x: x.name)
    ]
    dk = [SubscriptionKeywordItem(**x) for x in default_subscription_keywords()]
    dj = [SubscriptionJournalItem(**x) for x in default_subscription_journals()]
    dc = [SubscriptionConferenceItem(**x) for x in default_subscription_conferences()]
    return SubscriptionCatalogResponse(
        journals=journals,
        conferences=conferences,
        default_keywords=dk,
        default_journals=dj,
        default_conferences=dc,
    )


@router.get("/users/me/subscriptions/fetch-now")
def get_subscription_fetch_now(
    user_id: Annotated[str, Depends(current_user_id)],
    background_tasks: BackgroundTasks,
):
    """手动触发一次全库抓取（合并所有用户的期刊 RSS、会议 OpenAlex 等）。与定时任务相同逻辑。"""
    _ = user_id
    background_tasks.add_task(run_ingestion_standalone)
    return {"ok": True}


@router.get("/users/me/subscriptions", response_model=UserSubscriptionsResponse)
def get_my_subscriptions(
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
):
    u = db.get(UserProfile, user_id)
    if u is None:
        kw_j, j_j, c_j, csv = _default_profile_payload()
        u = UserProfile(
            user_id=user_id,
            keywords=csv,
            subscription_keywords_json=kw_j,
            subscription_journals_json=j_j,
            subscription_conferences_json=c_j,
        )
        db.add(u)
        db.commit()
    else:
        changed = _migrate_keywords_csv_to_json(u)
        if changed:
            u.keywords = keywords_csv_from_subscription_json(u.subscription_keywords_json)
            db.commit()

    return UserSubscriptionsResponse(
        keywords=_parse_keywords(u.subscription_keywords_json),
        journals=_parse_journals(u.subscription_journals_json),
        conferences=_parse_conferences(u.subscription_conferences_json),
    )


@router.put("/users/me/subscriptions", response_model=UserSubscriptionsResponse)
def put_my_subscriptions(
    user_id: Annotated[str, Depends(current_user_id)],
    body: UserSubscriptionsPut,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    kw_j = json.dumps(
        [k.model_dump() for k in body.keywords],
        ensure_ascii=False,
    )
    j_j = json.dumps([j.model_dump() for j in body.journals], ensure_ascii=False)
    c_j = json.dumps([c.model_dump() for c in body.conferences], ensure_ascii=False)
    csv = keywords_csv_from_subscription_json(kw_j)

    u = db.get(UserProfile, user_id)
    if u is None:
        u = UserProfile(
            user_id=user_id,
            keywords=csv,
            subscription_keywords_json=kw_j,
            subscription_journals_json=j_j,
            subscription_conferences_json=c_j,
        )
        db.add(u)
    else:
        u.keywords = csv
        u.subscription_keywords_json = kw_j
        u.subscription_journals_json = j_j
        u.subscription_conferences_json = c_j
    db.commit()
    background_tasks.add_task(run_ingestion_standalone)

    return UserSubscriptionsResponse(
        keywords=_parse_keywords(u.subscription_keywords_json),
        journals=_parse_journals(u.subscription_journals_json),
        conferences=_parse_conferences(u.subscription_conferences_json),
    )
