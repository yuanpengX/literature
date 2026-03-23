"""Feed 一句话总结：按用户缓存，后台补全（用户 LLM）。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Paper, PaperUserBlurb, UserProfile
from app.services.text_plain import heuristic_feed_blurb_from_abstract, strip_html_to_plain

logger = logging.getLogger(__name__)

BLURB_MAX = 120
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
    lines = ["请为下列论文各写一句中文内容总结（不超过80字），基于标题与摘要，不要编造。", ""]
    for p in papers:
        abst = strip_html_to_plain(p.abstract).replace("\n", " ")[:400]
        lines.append(f"id={p.id} | {p.title}")
        lines.append(f"摘要：{abst}")
        lines.append("")
    lines.append("仅输出 JSON：{\"items\":[{\"paper_id\":1,\"blurb\":\"...\"},...]}")
    user_prompt = "\n".join(lines)
    root = _normalize_llm_base(base_url)
    url = f"{root}/chat/completions"
    payload = {
        "model": model.strip(),
        "messages": [
            {
                "role": "system",
                "content": "只输出单个 JSON 对象，不要 markdown。",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    with httpx.Client(timeout=90.0) as client:
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


def merge_blurbs_into_feed_items(
    db: Session,
    user_id: str,
    items: list,  # list[PaperOut]
) -> None:
    """就地设置 feed_blurb（Pydantic model_copy）。"""
    ids = [it.id for it in items]
    m = load_blurbs_for_papers(db, user_id, ids)
    for i, it in enumerate(items):
        b = (m.get(it.id, "") or "").strip()
        if not b:
            b = heuristic_feed_blurb_from_abstract(it.abstract)
        items[i] = it.model_copy(update={"feed_blurb": b})


def generate_missing_blurbs_background(user_id: str, paper_ids: list[int]) -> None:
    """供 FastAPI BackgroundTasks 调用；独立 Session。"""
    from app.database import SessionLocal

    if user_id in ("", "anonymous") or not paper_ids:
        return
    db = SessionLocal()
    try:
        user = db.get(UserProfile, user_id)
        if (
            user is None
            or not (user.llm_api_key or "").strip()
            or not (user.llm_base_url or "").strip()
            or not (user.llm_model or "").strip()
        ):
            return
        existing = load_blurbs_for_papers(db, user_id, paper_ids)
        missing = [pid for pid in paper_ids if pid not in existing][:BATCH_MAX]
        if not missing:
            return
        stmt = select(Paper).where(Paper.id.in_(missing))
        papers = list(db.scalars(stmt).all())
        if not papers:
            return
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
            return
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
        db.commit()
    except Exception:
        logger.exception("feed_blurbs background user=%s", user_id)
        db.rollback()
    finally:
        db.close()
