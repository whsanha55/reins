# agent/watchdog.py — heartbeat watchdog(CRITICAL GAP, P1).
# running 상태 run 의 heartbeat_at 이 threshold 초과 → stalled + 티켓 todo 복귀 + telegram.
# 정상 lifecycle 종료는 status 가 succeeded/failed 로 바뀌므로 watchdog 미관여(가짜 알람 無).
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import render_card
from app.ticket.service import record_event

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from app.core.database import Database
    from app.core.notify.dispatcher import NotifyDispatcher

logger = logging.getLogger(__name__)


async def sweep(
    db: Database, dispatcher: NotifyDispatcher, stale_sec: int
) -> list[dict]:
    """정체 run 1회 스캔. now-stale_sec 이전 heartbeat 인 running run → stalled."""
    threshold = datetime.now(UTC) - timedelta(seconds=stale_sec)
    stale = await db.fetch(
        "SELECT id, ticket_id, heartbeat_at FROM agent_runs "
        "WHERE status='running' AND heartbeat_at < $1",
        threshold,
    )
    out = []
    for r in stale:
        rid = r["id"]
        tid = r["ticket_id"]
        await db.execute(
            "UPDATE agent_runs SET status='stalled', finished_at=now() WHERE id=$1", rid
        )
        # 티켓 progressing → todo 복귀(재클레임 가능). todo 가 아닌 상태면 미건드림.
        await db.execute(
            "UPDATE tickets SET status='todo', updated_at=now() "
            "WHERE id=$1 AND status='progressing'",
            tid,
        )
        await record_event(db, tid, "stalled", {"run_id": rid})
        msg = NotifyMessage(
            render_card(title=f"티켓 #{tid} 정체", body=f"run #{rid} heartbeat 정체", category="stalled")
        )
        await dispatcher.notify(
            category="stalled",
            payload_key=f"stalled:{rid}",
            message=msg,
            ticket_id=tid,
        )
        out.append({"run_id": rid, "ticket_id": tid})
    if out:
        logger.warning("watchdog stalled %d run(s)", len(out))
    return out


def schedule(
    scheduler: AsyncIOScheduler,
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    interval_sec: int,
    stale_sec: int,
) -> None:
    """가변 interval 로 watchdog 스케줄 등록. interval=0 → 미등록(off)."""
    if interval_sec <= 0:
        logger.info("watchdog disabled (interval=0)")
        return

    async def _tick() -> None:
        try:
            await sweep(db, dispatcher, stale_sec)
        except Exception:  # noqa: BLE001 — 스케줄 잡은 죽으면 안 됨
            logger.exception("watchdog sweep failed")

    scheduler.add_job(
        _tick,
        "interval",
        seconds=interval_sec,
        id="reins-watchdog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("watchdog scheduled interval=%ss stale=%ss", interval_sec, stale_sec)
