#!/usr/bin/env python3
"""
清空 arXiv / 期刊(RSS、OpenAlex) / 会议 等全部论文数据及推荐侧缓存，并立即执行一轮全量抓取。

用法（在 server 目录下）:
  python scripts/reset_papers_and_ingest.py
  python scripts/reset_papers_and_ingest.py --no-ingest   # 仅清空不抓取

需能访问外网（arXiv、RSS、api.openalex.org 等，视 .env 配置而定）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 包根: server/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete, func, select, text

import app.models  # noqa: F401 — 注册 ORM
from app.database import Base, SessionLocal, engine
from app.models import DailyPick, Paper, PaperStat, PaperUserBlurb
from app.services.ingest import run_all_ingestion


def clear_paper_related(db) -> None:
    """按依赖顺序删除，兼容未开启 SQLite FK 的环境。"""
    db.execute(delete(PaperUserBlurb))
    db.execute(delete(PaperStat))
    db.execute(delete(DailyPick))
    # 埋点里引用 paper_id 的先行处理，避免部分库上外键约束报错
    try:
        db.execute(text("UPDATE analytics_events SET paper_id = NULL WHERE paper_id IS NOT NULL"))
    except Exception:
        pass
    db.execute(delete(Paper))
    db.commit()


def main() -> int:
    Base.metadata.create_all(bind=engine)

    parser = argparse.ArgumentParser(description="清空论文与推荐缓存并可选手动触发抓取")
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="只清空数据库，不执行抓取",
    )
    args = parser.parse_args()

    if "sqlite" in str(engine.url).lower():
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

    def count_papers(sess) -> int:
        return int(sess.scalar(select(func.count()).select_from(Paper)) or 0)

    db = SessionLocal()
    try:
        n_before = count_papers(db)
        print(f"当前 papers 行数: {n_before}")
        clear_paper_related(db)
        n_after = count_papers(db)
        print(f"已清空；papers 行数: {n_after}")
    finally:
        db.close()

    if args.no_ingest:
        print("已跳过抓取（--no-ingest）。")
        return 0

    db2 = SessionLocal()
    try:
        print("开始全量抓取 run_all_ingestion …")
        out = run_all_ingestion(db2)
        print("抓取结果:", out)
        n_final = int(db2.scalar(select(func.count()).select_from(Paper)) or 0)
        print(f"完成后 papers 行数: {n_final}")
    finally:
        db2.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
