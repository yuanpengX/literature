"""Feed 一句话总结：按用户缓存，后台补全（用户 LLM）。"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Paper, PaperUserBlurb, UserProfile
from app.services.abstract_enrich import enrich_papers_for_feed_ids, refresh_feed_items_abstracts
from app.services.text_plain import strip_html_to_plain

logger = logging.getLogger(__name__)

BLURB_MAX = 680
BATCH_MAX = 10
_SYNC_BLURB_CAP = 32  # 单批 LLM 论文数硬上限，避免 prompt 过大


def _normalize_llm_base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u.lower().startswith("http"):
        raise ValueError("llm_base_url 须为 http(s)://")
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def _build_llm_blurbs_user_prompt(papers: list[Paper]) -> str:
    lines = [
        "请为下列每篇论文各写一段「简体中文」介绍，严格基于标题与摘要、不要编造。要求：",
        "① 必须使用简体中文（专有名词可保留英文）；禁止整段只用英文。",
        "② 固定为 2～3 个完整句子，用句号「。」分隔；结构：背景/问题 → 方法或要点 → 意义或结论（末句可省略）。",
        "③ 总长每篇不超过 260 字；④ 使用简洁书面语，勿用项目符号或编号列表。",
        "",
    ]
    for p in papers:
        abst = strip_html_to_plain(p.abstract).replace("\n", " ")[:650]
        lines.append(f"id={p.id} | {p.title}")
        if abst.strip():
            lines.append(f"摘要：{abst}")
        else:
            lines.append("摘要：（暂无）请仅依据标题写客观简短介绍，勿编造技术细节。")
        lines.append("")
    lines.append('仅输出 JSON：{"items":[{"paper_id":1,"blurb":"..."},...]}')
    return "\n".join(lines)


def _post_llm_blurbs_raw(
    base_url: str,
    api_key: str,
    model: str,
    papers: list[Paper],
    *,
    temperature: float,
) -> str:
    user_prompt = _build_llm_blurbs_user_prompt(papers)
    root = _normalize_llm_base(base_url)
    url = f"{root}/chat/completions"
    payload = {
        "model": model.strip(),
        "messages": [
            {
                "role": "system",
                "content": "你是学术文献编辑。blurb 必须为简体中文 2～3 句。只输出单个 JSON 对象，不要 markdown。",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(temperature),
    }
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    timeout = max(30.0, float(settings.feed_llm_http_timeout))
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _parse_llm_blurbs_json_content(text: str, valid: set[int]) -> dict[int, str]:
    t = text
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        t = m.group(1)
    s, e = t.find("{"), t.rfind("}")
    if s < 0 or e <= s:
        raise json.JSONDecodeError("no JSON object", text, 0)
    obj = json.loads(t[s : e + 1])
    items = obj.get("items")
    if not isinstance(items, list):
        return {}
    out: dict[int, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            pid = int(it.get("paper_id", it.get("id")))
        except (TypeError, ValueError):
            continue
        if pid not in valid:
            continue
        b = str(it.get("blurb") or "").strip()
        if len(b) > BLURB_MAX:
            b = b[: BLURB_MAX - 1] + "…"
        if b:
            out[pid] = b
    return out


def _call_llm_blurbs(
    base_url: str,
    api_key: str,
    model: str,
    papers: list[Paper],
) -> dict[int, str]:
    """调用用户 LLM；JSON 解析失败或缺项时有限次重试（降温 / 缩小批次）。"""
    if not papers:
        return {}
    want: set[int] = {p.id for p in papers}
    by_id = {p.id: p for p in papers}
    accumulated: dict[int, str] = {}
    missing_ids = [pid for pid in want]
    temperature = 0.2

    for attempt in range(4):
        work = [by_id[i] for i in missing_ids if i in by_id]
        if not work:
            break
        if attempt >= 2 and len(work) > 6:
            work = work[:6]
        valid = {p.id for p in work}
        try:
            raw_text = _post_llm_blurbs_raw(
                base_url, api_key, model, work, temperature=temperature
            )
            got = _parse_llm_blurbs_json_content(raw_text, valid)
        except json.JSONDecodeError as e:
            logger.warning(
                "feed_blurbs json decode attempt=%s papers=%s err=%s",
                attempt,
                len(work),
                e,
            )
            temperature = max(0.05, temperature - 0.05)
            continue
        except Exception as e:
            logger.warning(
                "feed_blurbs llm http attempt=%s papers=%s err=%s",
                attempt,
                len(work),
                e,
                exc_info=True,
            )
            temperature = max(0.05, temperature - 0.05)
            continue

        accumulated.update(got)
        if attempt == 0 and len(got) < len(work):
            logger.warning(
                "feed_blurbs partial llm missing=%s wanted=%s",
                len(work) - len(got),
                len(work),
            )
        missing_ids = [i for i in want if i not in accumulated]
        if not missing_ids:
            break
        temperature = max(0.05, temperature - 0.05)

    still = want - set(accumulated.keys())
    if still:
        logger.warning("feed_blurbs still_missing count=%s", len(still))
    return accumulated


def load_blurbs_for_papers(db: Session, user_id: str, paper_ids: list[int]) -> dict[int, str]:
    if not paper_ids or user_id in ("", "anonymous"):
        return {}
    stmt = select(PaperUserBlurb).where(
        PaperUserBlurb.user_id == user_id,
        PaperUserBlurb.paper_id.in_(paper_ids),
    )
    rows = db.scalars(stmt).all()
    return {r.paper_id: (r.blurb or "").strip() for r in rows if (r.blurb or "").strip()}


def ensure_blurbs_for_user_papers(
    db: Session,
    user_id: str,
    paper_ids: list[int],
    *,
    max_rounds: int = 48,
    batch_size: int | None = None,
) -> None:
    """
    同步多轮调用 LLM，尽力为 paper_ids 中缺失的条目写入 blurb（每轮最多 batch_size 篇）。
    """
    if not paper_ids or user_id in ("", "anonymous"):
        return
    user = db.get(UserProfile, user_id)
    if (
        user is None
        or not (user.llm_api_key or "").strip()
        or not (user.llm_base_url or "").strip()
        or not (user.llm_model or "").strip()
    ):
        return
    bs = BATCH_MAX if batch_size is None else max(1, min(int(batch_size), 32))
    stagnant = 0
    for _ in range(max_rounds):
        existing = load_blurbs_for_papers(db, user_id, paper_ids)
        missing = [pid for pid in paper_ids if pid not in existing]
        if not missing:
            return
        n = generate_missing_blurbs_for_user(db, user_id, missing, max_papers=bs)
        if n <= 0:
            stagnant += 1
            if stagnant >= 4:
                return
        else:
            stagnant = 0


def collect_feed_items_with_blurbs(
    db: Session,
    user_id: str,
    ordered: list,
    offset: int,
    limit: int,
    *,
    abstract_enrich_enabled: bool,
    max_scan_multiplier: int,
    wall_deadline_monotonic: float | None = None,
) -> tuple[list, int, bool]:
    """
    从 ordered 中自 offset 起顺序扫描，同步补全 LLM 摘要，直到凑满 limit 条均有非空 feed_blurb，
    或超出扫描窗口/候选耗尽/墙钟超时。返回 (items, next_index, blurbs_generation_incomplete)。
    incomplete 仅在为凑满 limit 且因墙钟提前退出时为 True。
    """
    out: list = []
    idx = max(0, int(offset))
    mult = max(1, int(max_scan_multiplier))
    max_scan = min(len(ordered), idx + max(limit * mult, limit + 5))

    sync_cap = max(BATCH_MAX, min(int(settings.feed_llm_blurb_sync_max), _SYNC_BLURB_CAP))

    hit_wall = False
    while len(out) < limit and idx < max_scan:
        if wall_deadline_monotonic is not None and time.monotonic() >= wall_deadline_monotonic:
            hit_wall = True
            break
        # 首屏首批拉大 batch，减少 LLM 往返（每日精选为单次调用，Feed 原先每批 10 篇易超时）
        if not out:
            chunk = min(sync_cap, len(ordered) - idx, max(limit, BATCH_MAX))
        else:
            chunk = BATCH_MAX
        batch_end = min(idx + max(chunk, 1), len(ordered))
        batch = ordered[idx:batch_end]
        if not batch:
            break
        ids = [it.id for it in batch]
        if abstract_enrich_enabled:
            enrich_papers_for_feed_ids(db, ids)
            refresh_feed_items_abstracts(db, batch)
        ensure_blurbs_for_user_papers(db, user_id, ids, batch_size=len(ids))
        merge_blurbs_into_feed_items(db, user_id, batch)
        advance = 0
        filled_limit = False
        for it in batch:
            advance += 1
            if (it.feed_blurb or "").strip():
                out.append(it)
                if len(out) >= limit:
                    idx += advance
                    filled_limit = True
                    break
        if filled_limit:
            break
        idx += len(batch)

    incomplete = bool(hit_wall and len(out) < limit)
    return out, idx, incomplete


def merge_blurbs_into_feed_items(
    db: Session,
    user_id: str,
    items: list,  # list[PaperOut]
) -> None:
    """就地设置 feed_blurb：仅用户 LLM 缓存，列表卡片不展示英文摘要启发式。"""
    ids = [it.id for it in items]
    m = load_blurbs_for_papers(db, user_id, ids)
    for i, it in enumerate(items):
        b = (m.get(it.id, "") or "").strip()
        items[i] = it.model_copy(update={"feed_blurb": b})


def _persist_blurbs(db: Session, user_id: str, got: dict[int, str]) -> None:
    now = datetime.now(timezone.utc)
    for pid, blurb in got.items():
        if not blurb:
            continue
        row = db.execute(
            select(PaperUserBlurb).where(
                PaperUserBlurb.user_id == user_id,
                PaperUserBlurb.paper_id == pid,
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(PaperUserBlurb(user_id=user_id, paper_id=pid, blurb=blurb, updated_at=now))
        else:
            row.blurb = blurb
            row.updated_at = now


def generate_missing_blurbs_for_user(
    db: Session,
    user_id: str,
    paper_ids: list[int],
    *,
    max_papers: int | None = None,
) -> int:
    """
    同步补全缺失的 LLM 一句话并 commit。返回本次写入的条数（可能小于 LLM 返回数）。
    max_papers 默认 BATCH_MAX；Feed 首屏可传更大以一次请求覆盖整页。
    """
    if user_id in ("", "anonymous") or not paper_ids:
        return 0
    user = db.get(UserProfile, user_id)
    if (
        user is None
        or not (user.llm_api_key or "").strip()
        or not (user.llm_base_url or "").strip()
        or not (user.llm_model or "").strip()
    ):
        return 0
    cap = BATCH_MAX if max_papers is None else max(1, int(max_papers))
    existing = load_blurbs_for_papers(db, user_id, paper_ids)
    missing = [pid for pid in paper_ids if pid not in existing][:cap]
    if not missing:
        return 0
    stmt = select(Paper).where(Paper.id.in_(missing))
    papers = list(db.scalars(stmt).all())
    if not papers:
        return 0
    try:
        got = _call_llm_blurbs(user.llm_base_url, user.llm_api_key, user.llm_model, papers)
    except Exception as e:
        logger.warning(
            "feed_blurbs llm failed user=%s papers=%s err=%s",
            user_id,
            len(papers),
            e,
            exc_info=True,
        )
        return 0
    if not got:
        return 0
    _persist_blurbs(db, user_id, got)
    db.commit()
    return len(got)


def generate_missing_blurbs_background(user_id: str, paper_ids: list[int]) -> None:
    """供 FastAPI BackgroundTasks 调用；独立 Session。"""
    from app.database import SessionLocal

    if user_id in ("", "anonymous") or not paper_ids:
        return
    db = SessionLocal()
    try:
        generate_missing_blurbs_for_user(db, user_id, paper_ids, max_papers=BATCH_MAX)
    except Exception:
        logger.exception("feed_blurbs background user=%s", user_id)
        db.rollback()
    finally:
        db.close()


def feed_blurbs_continue_after_index(
    user_id: str,
    ordered_ids: list[int],
    start_idx: int,
) -> None:
    """墙钟超时后从 ordered 的 start_idx 起继续补全 blurb（独立 Session）。"""
    from app.database import SessionLocal

    if user_id in ("", "anonymous"):
        return
    if start_idx < 0 or start_idx >= len(ordered_ids):
        return
    ids = [int(x) for x in ordered_ids[start_idx : start_idx + 300]]
    if not ids:
        return
    db = SessionLocal()
    try:
        ensure_blurbs_for_user_papers(
            db,
            user_id,
            ids,
            max_rounds=36,
            batch_size=BATCH_MAX,
        )
    except Exception:
        logger.exception("feed_blurbs continue_after_index user=%s", user_id[:24])
        db.rollback()
    finally:
        db.close()


def prewarm_feed_blurbs_for_user_background(user_id: str) -> None:
    """合并订阅候选 Top N 预热 LLM 摘要，减少 Feed 首屏冷启动。"""
    from app.database import SessionLocal
    from app.services.recommend import papers_to_feed_items
    from app.services.subscription_candidates import (
        filter_papers_by_user_subscriptions,
        merge_subscription_candidate_papers,
    )

    if user_id in ("", "anonymous"):
        return
    db = SessionLocal()
    try:
        user = db.get(UserProfile, user_id)
        if user is None:
            return
        if (
            not (user.llm_api_key or "").strip()
            or not (user.llm_base_url or "").strip()
            or not (user.llm_model or "").strip()
        ):
            return
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
        if not filtered:
            return
        ordered = papers_to_feed_items(filtered, user, "for_you")
        n = max(1, int(settings.feed_prewarm_top_n))
        ids = [p.id for p in ordered[:n]]
        ensure_blurbs_for_user_papers(
            db,
            user_id,
            ids,
            max_rounds=28,
            batch_size=BATCH_MAX,
        )
    except Exception:
        logger.exception("feed_blurbs prewarm user=%s", user_id[:24])
        db.rollback()
    finally:
        db.close()
