import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, SessionLocal, engine, ensure_papers_schema
import app.models  # noqa: F401 — 注册全部 ORM，供 create_all 建 fcm_tokens 等表
from app.routers import devices, events, feed, papers, prefs, search
from app.services.ingest import run_all_ingestion
from app.services.jobs import purge_old_events, purge_old_papers

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)
_scheduler: BackgroundScheduler | None = None


def _ingest_job() -> None:
    db = SessionLocal()
    try:
        out = run_all_ingestion(db)
        logger.info("ingestion %s", out)
    except Exception:
        logger.exception("ingestion failed")
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
    Base.metadata.create_all(bind=engine)
    ensure_papers_schema(engine)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _ingest_job)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_ingest_job, "interval", hours=2, id="ingest", replace_existing=True)
    _scheduler.add_job(_purge_job, "cron", hour=3, minute=10, id="purge", replace_existing=True)
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
app.include_router(feed.router, prefix=api_prefix)
app.include_router(papers.router, prefix=api_prefix)
app.include_router(search.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(prefs.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}
