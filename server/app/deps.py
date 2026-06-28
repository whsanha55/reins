# deps.py — FastAPI 의존성. db/dispatcher 는 app.state(lifespan 에서 생성).
from __future__ import annotations

from fastapi import Request

from app.core.database import Database
from app.core.notify.dispatcher import NotifyDispatcher


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_dispatcher(request: Request) -> NotifyDispatcher:
    return request.app.state.dispatcher
