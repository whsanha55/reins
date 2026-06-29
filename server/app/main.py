# main.py — FastAPI 앱 팩토리. lifespan: db pool · dispatcher · watchdog/digest 스케줄.
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.watchdog import schedule as schedule_watchdog
from app.api import agent, comments, decisions, deploy, ops, projects, telegram, tickets
from app.config import settings
from app.core.database import Database
from app.core.notify.dispatcher import NotifyDispatcher
from app.core.notify.router import NotifyRouter

logger = logging.getLogger(__name__)


def create_app(db: Database | None = None) -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _db = db or Database(settings.database_url)
    scheduler = AsyncIOScheduler(
        timezone="Asia/Seoul",
        job_defaults={"max_instances": 1, "misfire_grace_time": 60, "coalesce": True},
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await _db.initialize()
        app.state.db = _db
        # dispatcher = router + provisioner. token 미설정 시 notify 스킵(로컬).
        app.state.dispatcher = NotifyDispatcher(_db, NotifyRouter(_db))
        scheduler.start()
        # CRITICAL GAP: heartbeat watchdog(가변 interval, 0=off).
        schedule_watchdog(
            scheduler,
            _db,
            app.state.dispatcher,
            interval_sec=settings.WATCHDOG_INTERVAL_SEC,
            stale_sec=settings.WATCHDOG_STALE_SEC,
        )
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN unset — notify will be skipped")
        logger.info("reins API ready")
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)
            await _db.close()

    app = FastAPI(title="reins", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(projects.router)
    app.include_router(tickets.router)
    app.include_router(comments.router)
    app.include_router(decisions.router)
    app.include_router(deploy.router)
    app.include_router(agent.router)
    app.include_router(telegram.router)
    app.include_router(ops.router)
    return app


app = create_app()
