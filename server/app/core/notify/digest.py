# core/notify/digest.py — 아침 다이제스트(event log 집계, LLM 無 — D5).
# 완료/결정대기/정체 카운트 → HTML 카드 → dispatcher(category=digest).
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.notify.dispatcher import NotifyDispatcher
from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import render_card

if TYPE_CHECKING:
    from app.core.database import Database

logger = logging.getLogger(__name__)


async def build_and_dispatch(db: Database, dispatcher: NotifyDispatcher) -> dict:
    done = await db.fetchval("SELECT count(*) FROM tickets WHERE status='done'")
    pending = await db.fetchval("SELECT count(*) FROM decisions WHERE status='pending'")
    stalled = await db.fetchval("SELECT count(*) FROM agent_runs WHERE status='stalled'")
    failed = await db.fetchval("SELECT count(*) FROM agent_runs WHERE status='failed'")

    body = (
        f"완료: {done}\n"
        f"결정 대기: {pending}\n"
        f"정체 run: {stalled}\n"
        f"실패 run: {failed}"
    )
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    msg = NotifyMessage(render_card(title="아침 다이제스트", body=body, category="digest"))
    await dispatcher.notify(category="digest", payload_key=f"digest:{today}", message=msg)
    return {"done": done, "pending": pending, "stalled": stalled, "failed": failed, "date": today}
