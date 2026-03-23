import logging
import time
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.catalog.presets import user_subscription_keywords_list
from app.config import settings
from app.database import SessionLocal
from app.deps import current_user_id, get_db
from app.models import UserProfile
from app.schemas import FeedResponse
from app.services.feed_blurbs import (
    collect_feed_items_with_blurbs,
    feed_blurbs_continue_after_index,
)
from app.services.feed_hint import (
    FEED_PIPELINE_NOTE_ZH,
    build_feed_diagnostics,
    hint_after_collect,
    hint_for_no_llm,
    hint_for_zero_ordered,
)
from app.services.ingest import (
    maybe_fetch_arxiv_for_user_keywords,
    maybe_fetch_openalex_journal_for_user_keywords,
)
from app.services.recommend import papers_to_feed_items
from app.services.subscription_candidates import (
    filter_papers_by_user_subscriptions,
    merge_subscription_candidate_papers,
    paper_matches_feed_channel,
)
from app.services.user_defaults import default_subscription_fields

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])


def _log_user_prefix(uid: str) -> str:
    if not uid or uid == "anonymous":
        return uid or "anonymous"
    return uid[:20] + ("…" if len(uid) > 20 else "")


def _bg_maybe_fetch_arxiv(user_id: str, keywords: list[str]) -> None:
    db = SessionLocal()
    try:
        maybe_fetch_arxiv_for_user_keywords(db, user_id, keywords)
    except Exception:
        logger.exception("background arxiv keyword fetch failed user=%s", user_id[:24])
    finally:
        db.close()


def _bg_maybe_fetch_openalex_journal(user_id: str, keywords: list[str]) -> None:
    db = SessionLocal()
    try:
        maybe_fetch_openalex_journal_for_user_keywords(db, user_id, keywords)
    except Exception:
        logger.exception("background openalex journal fetch failed user=%s", user_id[:24])
    finally:
        db.close()

FeedSort = Literal["recommended", "recent", "hot", "for_you"]


def _channel_label(ch: str | None) -> str:
    if ch == "arxiv":
        return "arXiv"
    if ch == "journal":
        return "期刊"
    if ch == "conference":
        return "会议"
    return "全部"


@router.get("", response_model=FeedResponse)
def get_feed(
    background_tasks: BackgroundTasks,
    user_id: Annotated[str, Depends(current_user_id)],
    db: Session = Depends(get_db),
    cursor: str | None = Query(None, description="Offset string for pagination"),
    limit: int = Query(20, ge=1, le=100),
    sort: FeedSort = "recommended",
    channel: str | None = Query(
        None,
        description="arxiv | journal | conference；不传则不分频道（全部）",
    ),
):
    # 流水线（与 feed_pipeline_note 一致）：merge → 订阅预筛 → 频道 → papers_to_feed_items 排序 → collect LLM
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError:
            offset = 0

    raw = (channel or "").strip().lower()
    if not raw:
        ch = None
    elif raw in ("arxiv", "journal", "conference"):
        ch = raw
    else:
        raise HTTPException(status_code=400, detail="channel 须为 arxiv、journal 或 conference")

    logger.info(
        "feed request user=%s sort=%s channel=%s limit=%s offset=%s",
        _log_user_prefix(user_id),
        sort,
        ch,
        limit,
        offset,
    )

    user = db.get(UserProfile, user_id)
    if user is None and user_id != "anonymous":
        d = default_subscription_fields()
        user = UserProfile(
            user_id=user_id,
            keywords=d["keywords"],
            subscription_keywords_json=d["subscription_keywords_json"],
            subscription_journals_json=d["subscription_journals_json"],
            subscription_conferences_json=d["subscription_conferences_json"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if ch == "arxiv" and user_id != "anonymous" and user is not None:
        kws = user_subscription_keywords_list(user)
        if kws:
            # 外网抓取耗时不定，勿阻塞首字节，避免客户端误判为连接失败；下刷即可看到新数据
            background_tasks.add_task(_bg_maybe_fetch_arxiv, user_id, list(kws))

    if ch == "journal" and user_id != "anonymous" and user is not None:
        kws = user_subscription_keywords_list(user)
        if kws:
            background_tasks.add_task(_bg_maybe_fetch_openalex_journal, user_id, list(kws))

    merged = merge_subscription_candidate_papers(
        db,
        max_total=settings.feed_merge_max_total,
        per_channel_limit=settings.feed_merge_per_channel,
    )
    filtered = filter_papers_by_user_subscriptions(
        merged,
        user,
        strict=settings.feed_strict_subscription_filter,
    )
    papers = [p for p in filtered if paper_matches_feed_channel(p, ch)]
    ordered = papers_to_feed_items(papers, user, sort)

    conf_in_merged = sum(
        1 for p in merged if (p.source or "").startswith("openalex:conference")
    )
    conf_in_filtered = sum(
        1 for p in filtered if (p.source or "").startswith("openalex:conference")
    )
    conf_in_channel = sum(
        1 for p in papers if (p.source or "").startswith("openalex:conference")
    )
    logger.info(
        "feed pool user=%s channel=%s merged_total=%s filtered=%s channel_papers=%s "
        "ordered_out=%s conf_in_merged=%s conf_in_filtered=%s conf_in_channel=%s",
        _log_user_prefix(user_id),
        ch,
        len(merged),
        len(filtered),
        len(papers),
        len(ordered),
        conf_in_merged,
        conf_in_filtered,
        conf_in_channel,
    )

    blurbs_llm_ready = bool(
        user is not None
        and user_id != "anonymous"
        and (user.llm_api_key or "").strip()
        and (user.llm_base_url or "").strip()
        and (user.llm_model or "").strip()
    )

    diag_base = build_feed_diagnostics(
        len(merged),
        len(filtered),
        len(papers),
        len(ordered),
        None,
    )

    if not blurbs_llm_ready:
        hint_code, hint_msg = hint_for_no_llm(user_id, user)
        logger.info(
            "feed response empty reason=no_llm user=%s channel=%s anonymous=%s "
            "profile=%s has_base_url=%s has_api_key=%s has_model=%s strict_sub=%s",
            _log_user_prefix(user_id),
            ch,
            user_id == "anonymous",
            user is not None,
            bool(user and (user.llm_base_url or "").strip()),
            bool(user and (user.llm_api_key or "").strip()),
            bool(user and (user.llm_model or "").strip()),
            settings.feed_strict_subscription_filter,
        )
        return FeedResponse(
            items=[],
            next_cursor=None,
            blurbs_llm_ready=False,
            blurbs_generation_incomplete=False,
            feed_hint_code=hint_code,
            feed_hint_message=hint_msg,
            feed_pipeline_note=FEED_PIPELINE_NOTE_ZH,
            feed_diagnostics=diag_base,
        )

    if len(ordered) == 0:
        hint_code, hint_msg = hint_for_zero_ordered(
            len(merged),
            len(filtered),
            len(papers),
            _channel_label(ch),
            settings.feed_strict_subscription_filter,
        )
        logger.info(
            "feed response empty reason=zero_ordered user=%s hint=%s merged=%s filtered=%s papers=%s",
            _log_user_prefix(user_id),
            hint_code,
            len(merged),
            len(filtered),
            len(papers),
        )
        return FeedResponse(
            items=[],
            next_cursor=None,
            blurbs_llm_ready=True,
            blurbs_generation_incomplete=False,
            feed_hint_code=hint_code,
            feed_hint_message=hint_msg,
            feed_pipeline_note=FEED_PIPELINE_NOTE_ZH,
            feed_diagnostics=diag_base,
        )

    t0 = time.monotonic()
    wall_deadline = t0 + max(5.0, float(settings.feed_sync_wall_seconds))
    page, next_idx, blurbs_generation_incomplete, coll_stats = collect_feed_items_with_blurbs(
        db,
        user_id,
        ordered,
        offset,
        limit,
        abstract_enrich_enabled=settings.abstract_enrich_enabled,
        max_scan_multiplier=settings.feed_llm_ensure_max_scan_multiplier,
        wall_deadline_monotonic=wall_deadline,
    )
    elapsed = time.monotonic() - t0
    next_cursor = str(next_idx) if next_idx < len(ordered) else None

    if elapsed >= 25.0:
        logger.warning(
            "feed collect slow user=%s channel=%s limit=%s page_items=%s ordered=%s next_idx=%s "
            "next_cursor=%s incomplete=%s wall_s=%.1f elapsed=%.2fs",
            _log_user_prefix(user_id),
            ch,
            limit,
            len(page),
            len(ordered),
            next_idx,
            next_cursor,
            blurbs_generation_incomplete,
            float(settings.feed_sync_wall_seconds),
            elapsed,
        )
    else:
        logger.info(
            "feed collect done user=%s channel=%s limit=%s page_items=%s ordered=%s next_idx=%s "
            "next_cursor=%s incomplete=%s wall_s=%.1f elapsed=%.2fs",
            _log_user_prefix(user_id),
            ch,
            limit,
            len(page),
            len(ordered),
            next_idx,
            next_cursor,
            blurbs_generation_incomplete,
            float(settings.feed_sync_wall_seconds),
            elapsed,
        )

    if blurbs_generation_incomplete and user_id != "anonymous":
        ordered_ids = [p.id for p in ordered]
        if next_idx < len(ordered_ids):
            background_tasks.add_task(
                feed_blurbs_continue_after_index,
                user_id,
                ordered_ids,
                next_idx,
            )
            logger.info(
                "feed bg scheduled blurbs_continue user=%s from_idx=%s ordered_len=%s",
                _log_user_prefix(user_id),
                next_idx,
                len(ordered_ids),
            )

    hint_code, hint_msg = hint_after_collect(
        len(ordered),
        len(page),
        blurbs_generation_incomplete,
        coll_stats,
    )
    logger.info(
        "feed response hint user=%s code=%s page_items=%s batches=%s batches_no_blurb=%s",
        _log_user_prefix(user_id),
        hint_code,
        len(page),
        coll_stats.batches_processed,
        coll_stats.batches_zero_blurb_yield,
    )
    diag_full = build_feed_diagnostics(
        len(merged),
        len(filtered),
        len(papers),
        len(ordered),
        coll_stats,
    )

    return FeedResponse(
        items=page,
        next_cursor=next_cursor,
        blurbs_llm_ready=True,
        blurbs_generation_incomplete=blurbs_generation_incomplete,
        feed_hint_code=hint_code,
        feed_hint_message=hint_msg,
        feed_pipeline_note=FEED_PIPELINE_NOTE_ZH,
        feed_diagnostics=diag_full,
    )
