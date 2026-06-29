# decision/service.py — 결정 큐. 요청(에이전트) + idempotent resolve(웹).
# CRITICAL GAP: 중복 resolve 1회만 적용(UPDATE...WHERE status='pending' RETURNING).
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import GATE_LABEL, classify, render_card, resolve_keyboard
from app.ticket.service import record_event

if TYPE_CHECKING:
    from app.core.database import Database
    from app.core.notify.dispatcher import NotifyDispatcher

RESOLUTIONS = ("approved", "rejected", "changes")


class DecisionError(ValueError):
    pass


async def request_decision(
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    ticket_id: int,
    gate: str,
    summary: str,
    agent_run_id: int | None = None,
) -> dict:
    """에이전트 결정 요청 → pending decision + telegram 결정필요 핑."""
    category = classify(gate_type=gate)
    row = await db.fetchrow(
        "INSERT INTO decisions (ticket_id, gate, summary, status, agent_run_id) "
        "VALUES ($1, $2, $3, 'pending', $4) "
        "ON CONFLICT DO NOTHING RETURNING *",
        ticket_id,
        gate,
        summary,
        agent_run_id,
    )
    if row is None:
        # 이미 pending 동일 gate 존재 → 기존 반환(중복 요청 방지).
        row = await db.fetchrow(
            "SELECT * FROM decisions WHERE ticket_id=$1 AND gate=$2 AND status='pending'",
            ticket_id,
            gate,
        )
    d = dict(row)
    title = f"티켓 #{ticket_id} — {GATE_LABEL.get(gate, gate)} 결정"
    # 인라인 키보드 부착 — 사람이 텔레그램에서 바로 resolve(webhook 경유).
    msg = NotifyMessage(
        render_card(title=title, body=summary, category=category),
        reply_markup=resolve_keyboard(d["id"]),
    )
    await dispatcher.notify(
        category=category,
        payload_key=f"decision:{d['id']}",
        message=msg,
        ticket_id=ticket_id,
    )
    return d


async def list_decisions(db: Database, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.fetch(
            "SELECT * FROM decisions WHERE status=$1 ORDER BY created_at ASC",
            status,
        )
    else:
        rows = await db.fetch("SELECT * FROM decisions ORDER BY created_at ASC")
    return [dict(r) for r in rows]


async def resolve(
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    decision_id: int,
    resolution: str,
    note: str | None = None,
) -> dict:
    """idempotent resolve. 이미 resolved 면 applied=False 로 현재 상태 반환(에러 아님)."""
    if resolution not in RESOLUTIONS:
        raise DecisionError(f"resolution must be one of {RESOLUTIONS}")
    row = await db.fetchrow("SELECT * FROM decisions WHERE id=$1", decision_id)
    if not row:
        raise DecisionError(f"decision {decision_id} not found")

    # 핵심: pending 인 경우만 적용(원자적). 더블클릭/중복 → 2회째 applied=False.
    applied_id = await db.fetchval(
        "UPDATE decisions SET status=$1, resolution_note=$2, resolved_at=now() "
        "WHERE id=$3 AND status='pending' RETURNING id",
        resolution,
        note,
        decision_id,
    )
    applied = applied_id is not None
    if applied:
        await record_event(
            db,
            row["ticket_id"],
            "decision_resolved",
            {"decision_id": decision_id, "resolution": resolution, "note": note},
        )
        cat = "info"
        title = f"결정 #{decision_id} {resolution}"
        body = note or ""
        msg = NotifyMessage(render_card(title=title, body=body, category=cat))
        await dispatcher.notify(
            category=cat,
            payload_key=f"decision_resolved:{decision_id}:{resolution}",
            message=msg,
            ticket_id=row["ticket_id"],
        )
    return {
        "id": decision_id,
        "applied": applied,
        "status": resolution,
        "previous_status": row["status"],
    }
