import asyncio
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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


def configure_application_logging() -> None:
    """
    将 app.* 业务日志打到 stderr（Docker 默认可见），避免仅 Uvicorn access 无 Feed/ingest 细节。
    """
    app_root = logging.getLogger("app")
    if getattr(app_root, "_literature_logging_configured", False):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    app_root.addHandler(handler)
    app_root.setLevel(logging.INFO)
    # 处理完后不再冒泡到 root，避免与 Uvicorn 默认配置重复或级别不一致
    app_root.propagate = False
    # 降噪：HTTP 客户端 debug 勿刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    setattr(app_root, "_literature_logging_configured", True)
_scheduler: BackgroundScheduler | None = None
# 全量 ingest 可能超过 ingest_interval_hours；单飞避免并发写库，并与 APScheduler max_instances>1 配合，
# 使重叠触发尽快空跑返回，而不会出现 “maximum number of running instances reached” 整次跳过。
_ingest_lock = threading.Lock()


def _ingest_job() -> None:
    if not _ingest_lock.acquire(blocking=False):
        logger.info("ingest: skipped scheduled run because a previous ingest is still in progress")
        return
    try:
        run_ingestion_standalone()
    finally:
        _ingest_lock.release()


def _ingest_startup_background() -> None:
    """首启全量抓取耗时长，勿阻塞 lifespan，否则 Caddy 反代在窗口期内 connection refused → 502。"""
    if not _ingest_lock.acquire(blocking=False):
        logger.info("ingest: skipped startup run because another ingest is already in progress")
        return
    try:
        run_ingestion_standalone()
    except Exception:
        logger.exception("startup ingestion failed")
    finally:
        _ingest_lock.release()

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
    configure_application_logging()
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
        max_instances=3,
        coalesce=True,
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


class LiteratureAccessLogMiddleware(BaseHTTPMiddleware):
    """经 Caddy 反代时从 X-Forwarded-For 取客户端；用于与 docker logs 对照「手机是否打到 API」。"""

    async def dispatch(self, request: Request, call_next):
        ff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        ua = (request.headers.get("user-agent") or "")[:200].replace("\n", " ")
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            logger.info(
                "access %s %s %s ff=%s ua=%s",
                status_code,
                request.method,
                request.url.path,
                ff or "-",
                ua or "-",
            )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LiteratureAccessLogMiddleware)

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
