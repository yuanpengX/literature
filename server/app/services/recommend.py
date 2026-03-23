from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.catalog.presets import user_subscription_keywords_csv
from app.config import settings
from app.models import Paper, UserProfile
from app.schemas import PaperOut
from app.services.tokenize import interest_match_score


def _keyword_bonus(keywords_csv: str, title: str, abstract: str) -> float:
    if not keywords_csv.strip():
        return 0.0
    kws = [k.strip().lower() for k in keywords_csv.split(",") if k.strip()]
    if not kws:
        return 0.0
    blob = " ".join([title, abstract]).lower()
    hits = sum(1 for k in kws if k in blob)
    return min(1.0, hits * 0.25)


def _recency(p: Paper, now: datetime) -> float:
    ref = p.published_at or p.ingested_at
    if ref is None:
        return 0.5
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_days = (now - ref).total_seconds() / 86400.0
    return max(0.0, min(1.0, 1.0 - age_days / 60.0))


def _norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def papers_to_feed_items(
    papers: list[Paper],
    user: UserProfile | None,
    sort: str,
) -> list[PaperOut]:
    now = datetime.now(timezone.utc)
    user = user or UserProfile(user_id="_", keywords="", interest_blob="{}")
    blobs = user.interest_blob or "{}"
    kws = user_subscription_keywords_csv(user)

    hot_raw: list[float] = []
    interest_raw: list[float] = []
    recency_raw: list[float] = []
    for p in papers:
        h = p.stats.hot_score if p.stats is not None else 0.0
        hot_raw.append(h)
        ir = interest_match_score(blobs, p.title, p.abstract) + _keyword_bonus(kws, p.title, p.abstract)
        interest_raw.append(ir)
        recency_raw.append(_recency(p, now))

    hot_n = _norm(hot_raw)
    int_n = _norm(interest_raw)
    rec_n = _norm(recency_raw)

    scored: list[tuple[Paper, float, str | None]] = []
    for i, p in enumerate(papers):
        if sort == "recent":
            ref = p.published_at or p.ingested_at or now
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            scored.append((p, ref.timestamp(), None))
        else:
            final = (
                settings.recommend_alpha_hot * hot_n[i]
                + settings.recommend_beta_interest * int_n[i]
                + settings.recommend_gamma_recency * rec_n[i]
            )
            if hot_n[i] > int_n[i] + 0.12:
                reason = "trending"
            else:
                reason = "for_you"
            scored.append((p, final, reason))

    scored.sort(key=lambda x: x[1], reverse=True)

    out: list[PaperOut] = []
    for p, _, reason in scored:
        hs = p.stats.hot_score if p.stats is not None else 0.0
        rr = None if sort == "recent" else reason
        out.append(
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
                rank_reason=rr,  # type: ignore[arg-type]
            )
        )
    return out


def load_candidate_papers(
    db: Session,
    limit: int = 500,
    channel: str | None = None,
) -> list[Paper]:
    """
    channel:
      None — 全部（兼容旧客户端、本地摘要等）
      arxiv — 仅 arXiv
      journal — 期刊/综合：OpenAlex（含未细分）、RSS 订阅
      conference — OpenAlex 标记为会议的文献
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.paper_ttl_days)
    stmt = (
        select(Paper)
        .options(joinedload(Paper.stats))
        .where(Paper.ingested_at >= cutoff)
    )
    ch = (channel or "").strip().lower()
    if ch == "arxiv":
        stmt = stmt.where(Paper.source == "arxiv")
    elif ch == "journal":
        stmt = stmt.where(
            Paper.source != "arxiv",
            or_(
                Paper.source == "openalex",
                Paper.source.like("openalex:journal%"),
                Paper.source.like("rss:%"),
            ),
        )
    elif ch == "conference":
        stmt = stmt.where(
            Paper.source != "arxiv",
            Paper.source.like("openalex:conference%"),
        )

    stmt = stmt.order_by(Paper.published_at.desc().nulls_last(), Paper.id.desc()).limit(limit)
    return list(db.scalars(stmt).unique().all())
