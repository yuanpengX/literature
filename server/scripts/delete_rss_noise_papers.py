#!/usr/bin/env python3
"""
手动删除库中「期刊 RSS 噪声」论文（标题与 ingest 中 _rss_title_is_noise 规则一致）。
不影响 arXiv / OpenAlex 等非 rss: 来源。

用法（在 server 目录下）:
  python scripts/delete_rss_noise_papers.py
  python scripts/delete_rss_noise_papers.py --dry-run   # 只打印将删除的 id/title

Docker 示例:
  docker compose -f ../docker-compose.yml run --rm literature-api \\
    python scripts/delete_rss_noise_papers.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import app.models  # noqa: F401
from sqlalchemy import delete, select, text

from app.database import Base, SessionLocal, engine
from app.models import Paper, PaperStat, PaperUserBlurb
from app.services.ingest import _rss_title_is_noise


def _chunked(ids: list[int], size: int) -> list[list[int]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="删除 RSS 噪声论文行")
    parser.add_argument("--dry-run", action="store_true", help="仅列出，不写库")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    if "sqlite" in str(engine.url).lower():
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

    db = SessionLocal()
    try:
        rows = list(db.scalars(select(Paper).where(Paper.source.like("rss:%"))).all())
        victims = [p for p in rows if _rss_title_is_noise(p.title or "")]
        print(f"RSS 论文共 {len(rows)} 条，命中噪声规则 {len(victims)} 条")
        for p in victims[:50]:
            print(f"  id={p.id} title={p.title!r}")
        if len(victims) > 50:
            print(f"  ... 另有 {len(victims) - 50} 条")
        if args.dry_run or not victims:
            return 0

        ids = [p.id for p in victims]
        for chunk in _chunked(ids, 400):
            db.execute(delete(PaperUserBlurb).where(PaperUserBlurb.paper_id.in_(chunk)))
            db.execute(delete(PaperStat).where(PaperStat.paper_id.in_(chunk)))
        try:
            for chunk in _chunked(ids, 400):
                placeholders = ",".join(str(i) for i in chunk)
                db.execute(text(f"UPDATE analytics_events SET paper_id = NULL WHERE paper_id IN ({placeholders})"))
        except Exception:
            pass
        for chunk in _chunked(ids, 400):
            db.execute(delete(Paper).where(Paper.id.in_(chunk)))
        db.commit()
        print(f"已删除 {len(ids)} 条。")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
