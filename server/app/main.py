import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    Base,
    SessionLocal,
    engine,
    ensure_papers_schema,
    ensure_user_llm_columns,
    ensure_user_subscription_columns,
)
import app.models  # noqa: F401 — 注册全部 ORM，供 create_all 建 fcm_tokens 等表
from app.routers import auth_wechat, client_config, daily_picks, devices, events, feed, papers, prefs, search, subscriptions
from app.services.daily_picks import run_daily_picks_for_all_users
from app.services.ingest import run_ingestion_standalone
from app.services.jobs import purge_old_events, purge_old_papers
from app.config import settings
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)
_scheduler: BackgroundScheduler | None = None


def _ingest_job() -> None:
    run_ingestion_standalone()


def _ingest_startup_background() -> None:
    """首启全量抓取耗时长，勿阻塞 lifespan，否则 Caddy 反代在窗口期内 connection refused → 502。"""
    try:
        _ingest_job()
    except Exception:
        logger.exception("startup ingestion failed")

def _daily_picks_job() -> None:
    db = SessionLocal()
    try:
        n = run_daily_picks_for_all_users(db)
        logger.info("daily_picks finished users_touched=%s", n)
    except Exception:
        logger.exception("daily_picks job failed")
    finally:
        db.close()


def _purge_job() -> None:
    db = SessionLocal()
    try:
        p = purge_old_papers(db)
        e = purge_old_events(db)
        logger.info("purge papers=%s events=%s", p, e)
    except Exception:
        logger.exception("purge failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    # uvicorn 完成日志初始化后再调，否则 root 级别可能挡住 app 的 INFO
    logging.getLogger("app").setLevel(logging.INFO)
    Base.metadata.create_all(bind=engine)
    ensure_papers_schema(engine)
    ensure_user_llm_columns(engine)
    ensure_user_subscription_columns(engine)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _ingest_startup_background)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _ingest_job,
        "interval",
        hours=float(settings.ingest_interval_hours),
        id="ingest",
        replace_existing=True,
    )
    _scheduler.add_job(_purge_job, "cron", hour=3, minute=10, id="purge", replace_existing=True)
    try:
        tz = ZoneInfo(settings.daily_picks_timezone)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
    _scheduler.add_job(
        _daily_picks_job,
        CronTrigger(
            hour=settings.daily_picks_hour,
            minute=settings.daily_picks_minute,
            timezone=tz,
        ),
        id="daily_picks",
        replace_existing=True,
    )
    _scheduler.start()

    yield

    if _scheduler:
        _scheduler.shutdown(wait=False)
    _executor.shutdown(wait=False)


app = FastAPI(title="Literature Radar API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(auth_wechat.router, prefix=api_prefix)
app.include_router(client_config.router, prefix=api_prefix)
app.include_router(feed.router, prefix=api_prefix)
app.include_router(papers.router, prefix=api_prefix)
app.include_router(search.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(prefs.router, prefix=api_prefix)
app.include_router(subscriptions.router, prefix=api_prefix)
app.include_router(daily_picks.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}
