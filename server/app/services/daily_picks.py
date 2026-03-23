"""每日精选：合并 arXiv/期刊/会议候选，按用户关键词筛选后调用用户自备 LLM 选出 10 篇。"""

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
from app.schemas import PaperOut
from app.services.recommend import load_candidate_papers

logger = logging.getLogger(__name__)


def _pick_date_str() -> str:
    try:
        tz = ZoneInfo(settings.daily_picks_timezone)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
    return datetime.now(tz).date().isoformat()


def _merge_channel_candidates(db: Session, max_total: int) -> list[Paper]:
    seen: set[int] = set()
    out: list[Paper] = []
    for ch in ("arxiv", "journal", "conference"):
        for p in load_candidate_papers(db, limit=120, channel=ch):
            if p.id in seen:
                continue
            seen.add(p.id)
            out.append(p)
            if len(out) >= max_total:
                return out
    return out


def _filter_by_keywords(papers: list[Paper], keywords_csv: str) -> list[Paper]:
    kws = [k.strip().lower() for k in (keywords_csv or "").split(",") if k.strip()]
    if not kws:
        return papers[: settings.daily_picks_max_candidates]
    matched: list[Paper] = []
    for p in papers:
        blob = f"{p.title} {p.abstract}".lower()
        if any(k in blob for k in kws):
            matched.append(p)
    if not matched:
        return papers[: settings.daily_picks_max_candidates]
    return matched[: settings.daily_picks_max_candidates]


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
        lines.append(f"- id={p.id} | 通道={ch} | 标题={p.title}")
        lines.append(f"  摘要节选：{abst}")
        lines.append("")
    lines.append(
        "请从这些候选中选出恰好 10 篇最值得该用户阅读的论文（若不足 10 篇则只返回实际数量）。"
        "优先与关键词相关，并兼顾质量、新颖度与多样性（arXiv/期刊/会议可兼顾）。"
    )
    lines.append('仅输出一个 JSON 对象，不要 markdown 代码块，格式：{"paper_ids":[整数,...],"note":"一句中文简要说明"}')
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
                "content": "你是学术文献策展助手。只输出单个 JSON 对象，键为 paper_ids 与 note，不要其它文字。",
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


def _parse_llm_choice_ids(raw: str, valid_ids: set[int]) -> tuple[list[int], str]:
    obj = _extract_json_obj(raw)
    raw_ids = obj.get("paper_ids") or obj.get("ids") or []
    note = str(obj.get("note") or obj.get("reason") or "").strip()
    out: list[int] = []
    for x in raw_ids:
        try:
            pid = int(x)
        except (TypeError, ValueError):
            continue
        if pid in valid_ids and pid not in out:
            out.append(pid)
        if len(out) >= 10:
            break
    return out, note


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

    merged = _merge_channel_candidates(db, settings.daily_picks_max_candidates * 2)
    kcsv = user_subscription_keywords_csv(user)
    candidates = _filter_by_keywords(merged, kcsv)
    if len(candidates) < 1:
        _upsert_daily_pick(
            db,
            user.user_id,
            pick_date,
            [],
            "",
            error_message="候选论文为空，请先完成抓取或放宽关键词",
        )
        db.commit()
        return

    valid_ids = {p.id for p in candidates}
    prompt = _build_user_prompt(kcsv, candidates)
    try:
        raw = _call_user_llm(user.llm_base_url, user.llm_api_key, user.llm_model, prompt)
        ids, note = _parse_llm_choice_ids(raw, valid_ids)
        if not ids:
            raise ValueError("LLM 未返回有效 paper_ids")
        _upsert_daily_pick(db, user.user_id, pick_date, ids, note, error_message=None)
    except Exception as e:
        logger.warning("daily_pick user=%s failed: %s", user.user_id, e)
        _upsert_daily_pick(db, user.user_id, pick_date, [], "", error_message=str(e)[:2000])
    db.commit()


def _upsert_daily_pick(
    db: Session,
    user_id: str,
    pick_date: str,
    paper_ids: list[int],
    note: str,
    error_message: str | None,
) -> None:
    row = db.execute(
        select(DailyPick).where(DailyPick.user_id == user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    payload = json.dumps(paper_ids, ensure_ascii=False)
    if row is None:
        db.add(
            DailyPick(
                user_id=user_id,
                pick_date=pick_date,
                paper_ids_json=payload,
                curator_note=note or "",
                error_message=error_message,
            )
        )
    else:
        row.paper_ids_json = payload
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


def load_daily_pick_papers(db: Session, user_id: str, pick_date: str) -> tuple[list[PaperOut], str | None, str | None]:
    """返回 (有序论文, 策展说明, 错误信息)。"""
    row = db.execute(
        select(DailyPick).where(DailyPick.user_id == user_id, DailyPick.pick_date == pick_date)
    ).scalar_one_or_none()
    if row is None:
        return [], None, None
    if row.error_message:
        return [], row.curator_note or None, row.error_message
    try:
        ids = json.loads(row.paper_ids_json or "[]")
    except json.JSONDecodeError:
        return [], None, "解析 paper_ids 失败"
    if not isinstance(ids, list) or not ids:
        return [], row.curator_note or None, row.error_message
    stmt = select(Paper).options(joinedload(Paper.stats)).where(Paper.id.in_(ids))
    by_id = {p.id: p for p in db.scalars(stmt).unique().all()}
    ordered: list[PaperOut] = []
    for i in ids:
        try:
            pid = int(i)
        except (TypeError, ValueError):
            continue
        p = by_id.get(pid)
        if p is None:
            continue
        hs = p.stats.hot_score if p.stats is not None else 0.0
        ordered.append(
            PaperOut(
                id=p.id,
                external_id=p.external_id,
                title=p.title,
                abstract=p.abstract,
                pdf_url=p.pdf_url,
                html_url=p.html_url,
                source=p.source,
                primary_category=p.primary_category,
                published_at=p.published_at,
                citation_count=p.citation_count,
                hot_score=hs,
                rank_reason="recent",
            )
        )
    return ordered, row.curator_note or None, None
