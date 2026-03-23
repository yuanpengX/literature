"""Feed 一句话总结：按用户缓存，后台补全（用户 LLM）。"""

from __future__ import annotations

import json
import logging
import re
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


def _normalize_llm_base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u.lower().startswith("http"):
        raise ValueError("llm_base_url 须为 http(s)://")
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def _call_llm_blurbs(
    base_url: str,
    api_key: str,
    model: str,
    papers: list[Paper],
) -> dict[int, str]:
    if not papers:
        return {}
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
    user_prompt = "\n".join(lines)
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
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    timeout = max(30.0, float(settings.feed_llm_http_timeout))
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return {}
    msg = choices[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    t = text
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        t = m.group(1)
    s, e = t.find("{"), t.rfind("}")
    if s < 0 or e <= s:
        return {}
    obj = json.loads(t[s : e + 1])
    items = obj.get("items")
    if not isinstance(items, list):
        return {}
    valid = {p.id for p in papers}
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
    batch_size: int = BATCH_MAX,
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
    stagnant = 0
    for _ in range(max_rounds):
        existing = load_blurbs_for_papers(db, user_id, paper_ids)
        missing = [pid for pid in paper_ids if pid not in existing]
        if not missing:
            return
        n = generate_missing_blurbs_for_user(db, user_id, missing, max_papers=batch_size)
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
) -> tuple[list, int]:
    """
    从 ordered 中自 offset 起顺序扫描，同步补全 LLM 摘要，直到凑满 limit 条均有非空 feed_blurb，
    或超出扫描窗口/候选耗尽。返回 (items, next_index)。
    """
    out: list = []
    idx = max(0, int(offset))
    mult = max(1, int(max_scan_multiplier))
    max_scan = min(len(ordered), idx + max(limit * mult, limit + 5))

    while len(out) < limit and idx < max_scan:
        batch_end = min(idx + BATCH_MAX, len(ordered))
        batch = ordered[idx:batch_end]
        if not batch:
            break
        ids = [it.id for it in batch]
        if abstract_enrich_enabled:
            enrich_papers_for_feed_ids(db, ids)
            refresh_feed_items_abstracts(db, batch)
        ensure_blurbs_for_user_papers(db, user_id, ids)
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

    return out, idx


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
