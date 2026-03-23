"""每日精选：合并订阅相关候选（关键词/期刊 RSS/会议 venue），预筛后调用用户自备 LLM 选出至多 10 篇，并附每篇一句推荐理由。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.catalog.presets import user_subscription_keywords_csv
from app.config import settings
from app.models import DailyPick, Paper, UserProfile
from app.schemas import DailyPickItemOut, PaperOut
from app.services.recommend import paper_to_out
from app.services.subscription_candidates import (
    filter_papers_by_user_subscriptions,
    merge_subscription_candidate_papers,
)

logger = logging.getLogger(__name__)

BLURB_MAX_LEN = 100


def _pick_date_str() -> str:
    try:
        tz = ZoneInfo(settings.daily_picks_timezone)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
    return datetime.now(tz).date().isoformat()


def _normalize_llm_base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u.lower().startswith("http"):
        raise ValueError("llm_base_url 须为 http:// 或 https:// 开头")
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def _build_user_prompt(keywords_csv: str, papers: list[Paper]) -> str:
    kws = keywords_csv.strip() or "（用户未设置关键词，请综合新颖度与泛读价值）"
    lines = [
        f"用户关注关键词：{kws}",
        "",
        "候选论文（请严格使用下列 id 数字，不要编造 id）：",
    ]
    lim = max(200, settings.daily_picks_abstract_chars)
    for p in papers:
        abst = (p.abstract or "").replace("\n", " ").strip()[:lim]
        ch = p.source or "?"
        au = (p.authors_text or "").strip()
        if au:
            lines.append(f"- id={p.id} | 通道={ch} | 作者={au} | 标题={p.title}")
        else:
            lines.append(f"- id={p.id} | 通道={ch} | 标题={p.title}")
        lines.append(f"  摘要节选：{abst}")
        lines.append("")
    lines.append(
        "请从这些候选中选出至多 10 篇最值得该用户阅读的论文（可少于 10）。"
        "优先与关键词相关，并兼顾质量、新颖度与多样性。"
        f"每一篇必须给一句中文推荐理由（不超过{BLURB_MAX_LEN}字），不要编造事实。"
    )
    lines.append(
        "仅输出一个 JSON 对象，不要 markdown 代码块。格式示例："
        '{"picks":[{"paper_id":123,"blurb":"一句推荐理由"},...],"note":"对今日选集的整体一句说明"}'
    )
    return "\n".join(lines)


def _extract_json_obj(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        t = m.group(1)
    s = t.find("{")
    e = t.rfind("}")
    if s < 0 or e <= s:
        raise ValueError("响应中未找到 JSON 对象")
    return json.loads(t[s : e + 1])


def _call_user_llm(base_url: str, api_key: str, model: str, user_prompt: str) -> str:
    root = _normalize_llm_base(base_url)
    url = f"{root}/chat/completions"
    payload = {
        "model": model.strip(),
        "messages": [
            {
                "role": "system",
                "content": "你是学术文献策展助手。只输出单个 JSON 对象，含 picks 数组（paper_id、blurb）与可选 note，不要其它文字。",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.25,
    }
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("LLM 返回无 choices")
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _parse_llm_daily_response(obj: dict, valid_ids: set[int]) -> tuple[list[tuple[int, str]], str]:
    note = str(obj.get("note") or obj.get("reason") or "").strip()
    picks = obj.get("picks")
    if isinstance(picks, list) and picks:
        out: list[tuple[int, str]] = []
        seen: set[int] = set()
        for item in picks:
            if not isinstance(item, dict):
                continue
            raw_pid = item.get("paper_id", item.get("id"))
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                continue
            if pid not in valid_ids or pid in seen:
                continue
            blurb = str(item.get("blurb") or item.get("why") or "").strip()
            if len(blurb) > BLURB_MAX_LEN:
                blurb = blurb[: BLURB_MAX_LEN - 1] + "…"
            out.append((pid, blurb))
            seen.add(pid)
            if len(out) >= 10:
                break
        if out:
            return out, note

    raw_ids = obj.get("paper_ids") or obj.get("ids") or []
    legacy: list[int] = []
    for x in raw_ids:
        try:
            pid = int(x)
        except (TypeError, ValueError):
            continue
        if pid in valid_ids and pid not in legacy:
            legacy.append(pid)
        if len(legacy) >= 10:
            break
    return [(pid, "") for pid in legacy], note


def _stored_payload_from_pairs(pairs: list[tuple[int, str]]) -> str:
    return json.dumps(
        [{"paper_id": a, "blurb": b} for a, b in pairs],
        ensure_ascii=False,
    )


def _parse_stored_daily_items(json_str: str) -> tuple[list[int], dict[int, str]]:
    try:
        data = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return [], {}
    if not isinstance(data, list) or not data:
        return [], {}
    if all(isinstance(x, int) for x in data):
        return [int(x) for x in data], {}
    ids: list[int] = []
    blurbs: dict[int, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        raw = item.get("paper_id", item.get("id"))
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        ids.append(pid)
        b = str(item.get("blurb") or "").strip()[:200]
        blurbs[pid] = b
    return ids, blurbs


def generate_daily_pick_for_user(db: Session, user: UserProfile, pick_date: str | None = None) -> None:
    pick_date = pick_date or _pick_date_str()
    if not user.llm_api_key.strip() or not user.llm_base_url.strip() or not user.llm_model.strip():
        return

    existing = db.execute(
        select(DailyPick).where(DailyPick.user_id == user.user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    if existing and not existing.error_message:
        try:
            cur = json.loads(existing.paper_ids_json or "[]")
        except json.JSONDecodeError:
            cur = []
        if isinstance(cur, list) and len(cur) > 0:
            return

    merged = merge_subscription_candidate_papers(
        db,
        max_total=max(settings.daily_picks_max_candidates * 4, 120),
        per_channel_limit=150,
    )
    candidates = filter_papers_by_user_subscriptions(merged, user, strict=False)
    candidates = candidates[: max(settings.daily_picks_max_candidates * 2, 64)]
    kcsv = user_subscription_keywords_csv(user)
    if len(candidates) < 1:
        _upsert_daily_pick_payload(
            db,
            user.user_id,
            pick_date,
            "[]",
            "",
            error_message="候选论文为空，请先完成抓取或调整订阅（关键词/期刊/会议）",
        )
        db.commit()
        return

    valid_ids = {p.id for p in candidates}
    prompt = _build_user_prompt(kcsv, candidates)
    try:
        raw = _call_user_llm(user.llm_base_url, user.llm_api_key, user.llm_model, prompt)
        obj = _extract_json_obj(raw)
        pairs, note = _parse_llm_daily_response(obj, valid_ids)
        if not pairs:
            raise ValueError("LLM 未返回有效 picks 或 paper_ids")
        payload = _stored_payload_from_pairs(pairs)
        _upsert_daily_pick_payload(db, user.user_id, pick_date, payload, note, error_message=None)
    except Exception as e:
        logger.warning("daily_pick user=%s failed: %s", user.user_id, e)
        _upsert_daily_pick_payload(db, user.user_id, pick_date, "[]", "", error_message=str(e)[:2000])
    db.commit()


def _upsert_daily_pick_payload(
    db: Session,
    user_id: str,
    pick_date: str,
    paper_ids_json: str,
    note: str,
    error_message: str | None,
) -> None:
    row = db.execute(
        select(DailyPick).where(DailyPick.user_id == user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    if row is None:
        db.add(
            DailyPick(
                user_id=user_id,
                pick_date=pick_date,
                paper_ids_json=paper_ids_json,
                curator_note=note or "",
                error_message=error_message,
            )
        )
    else:
        row.paper_ids_json = paper_ids_json
        row.curator_note = note or ""
        row.error_message = error_message


def run_daily_picks_for_all_users(db: Session) -> int:
    users = list(db.scalars(select(UserProfile)).all())
    n = 0
    pick_date = _pick_date_str()
    for u in users:
        if not u.llm_api_key.strip() or not u.llm_base_url.strip() or not u.llm_model.strip():
            continue
        try:
            generate_daily_pick_for_user(db, u, pick_date)
            n += 1
        except Exception:
            logger.exception("daily_pick fatal user=%s", u.user_id)
            db.rollback()
    return n


def load_daily_pick_items(
    db: Session, user_id: str, pick_date: str
) -> tuple[list[DailyPickItemOut], str | None, str | None]:
    row = db.execute(
        select(DailyPick).where(DailyPick.user_id == user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    if row is None:
        return [], None, None
    if row.error_message:
        return [], row.curator_note or None, row.error_message
    ids, blurbs = _parse_stored_daily_items(row.paper_ids_json or "[]")
    if not ids:
        return [], row.curator_note or None, row.error_message
    stmt = select(Paper).options(joinedload(Paper.stats)).where(Paper.id.in_(ids))
    by_id = {p.id: p for p in db.scalars(stmt).unique().all()}
    ordered: list[DailyPickItemOut] = []
    for pid in ids:
        p = by_id.get(pid)
        if p is None:
            continue
        hs = p.stats.hot_score if p.stats is not None else 0.0
        po = paper_to_out(p, "recent", hs, rank_tags=[], feed_blurb="")
        ordered.append(DailyPickItemOut(paper=po, pick_blurb=blurbs.get(pid, "")))
    return ordered, row.curator_note or None, None
