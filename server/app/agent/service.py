# agent/service.py — 로컬 에이전트 지원. 원자적 클레임 + heartbeat + 결과(스키마검증) + lifecycle.
# CRITICAL GAP: 원자적 클레임(FOR UPDATE SKIP LOCKED) + malformed 결과 → 카드 정지(D7-B).
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import render_card
from app.decision.service import request_decision
from app.ticket.service import record_event, transition_ticket
from app.ticket.state import ResultValidationError, validate_agent_result

if TYPE_CHECKING:
    from app.core.database import Database
    from app.core.notify.dispatcher import NotifyDispatcher

LIFECYCLE = {"running", "succeeded", "failed", "stalled"}


class AgentError(ValueError):
    pass


async def claim(
    db: Database, *, project_id: int | None = None
) -> dict | None:
    """원자적 클레임: todo 한 건 → progressing + agent_run(running) 생성. 동시 → 1 승자."""
    row = await db.fetchrow(
        "UPDATE tickets SET status='progressing', updated_at=now() "
        "WHERE id = ("
        "  SELECT id FROM tickets "
        "  WHERE status='todo' AND ($1::int IS NULL OR project_id=$1) "
        "  ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
        ") RETURNING *",
        project_id,
    )
    if not row:
        return None
    ticket = dict(row)
    run_id = await db.fetchval(
        "INSERT INTO agent_runs (ticket_id, status, heartbeat_at) "
        "VALUES ($1, 'running', now()) RETURNING id",
        ticket["id"],
    )
    await record_event(db, ticket["id"], "claimed", {"run_id": run_id})
    return {"ticket": ticket, "run_id": run_id}


async def heartbeat(db: Database, run_id: int) -> bool:
    val = await db.fetchval(
        "UPDATE agent_runs SET heartbeat_at=now() WHERE id=$1 AND status='running' RETURNING id",
        run_id,
    )
    return val is not None


async def submit_result(
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    run_id: int,
    payload: dict,
) -> dict:
    """에이전트 결과 push. 스키마 검증 → 전이/결정요청. malformed → run failed, 카드 정지."""
    run = await db.fetchrow("SELECT * FROM agent_runs WHERE id=$1", run_id)
    if not run:
        raise AgentError(f"run {run_id} not found")
    ticket_id = run["ticket_id"]

    # D6/D7-B: 서버가 결과 스키마 검증. malformed → run failed, 카드 이동 無.
    try:
        validated = validate_agent_result(payload)
    except ResultValidationError as e:
        await _fail_run(db, dispatcher, run_id, ticket_id, f"result schema: {e}")
        return {"run_id": run_id, "status": "failed", "reason": str(e)}

    status = validated["status"]
    await db.execute(
        "UPDATE agent_runs SET status=$1, finished_at=now(), heartbeat_at=now(), "
        "result=$2::jsonb WHERE id=$3",
        status,
        json.dumps(validated, ensure_ascii=False),
        run_id,
    )

    if validated.get("diff_url"):
        await record_event(
            db, ticket_id, "diff", {"url": validated["diff_url"], "run_id": run_id}
        )

    if status == "succeeded":
        gate = validated.get("gate")
        if gate:
            # 4게이트 → 결정 요청. 티켓은 progressing 유지(결정 대기).
            await request_decision(
                db,
                dispatcher,
                ticket_id=ticket_id,
                gate=gate,
                summary=validated.get("gate_summary") or validated["summary"],
                agent_run_id=run_id,
            )
            await record_event(db, ticket_id, "gate_requested", {"gate": gate})
            return {"run_id": run_id, "status": "succeeded", "gate": gate}
        # 게이트 없는 성공 → ready_for_qa
        await transition_ticket(
            db, dispatcher, ticket_id=ticket_id, to="qa", actor="agent",
            note=validated["summary"],
        )
        return {"run_id": run_id, "status": "succeeded", "to": "qa"}

    # failed
    await record_event(
        db, ticket_id, "agent_failed", {"run_id": run_id, "summary": validated["summary"]}
    )
    msg = NotifyMessage(
        render_card(
            title=f"티켓 #{ticket_id} 에이전트 실패",
            body=validated["summary"],
            category="info",
        )
    )
    await dispatcher.notify(
        category="info",
        payload_key=f"agent_failed:{run_id}",
        message=msg,
        ticket_id=ticket_id,
    )
    return {"run_id": run_id, "status": "failed"}


async def _fail_run(
    db: Database, dispatcher: NotifyDispatcher, run_id: int, ticket_id: int, reason: str
) -> None:
    await db.execute(
        "UPDATE agent_runs SET status='failed', finished_at=now() WHERE id=$1", run_id
    )
    await record_event(db, ticket_id, "agent_failed", {"run_id": run_id, "reason": reason})
    msg = NotifyMessage(
        render_card(title=f"티켓 #{ticket_id} 결과 검증 실패", body=reason, category="info")
    )
    await dispatcher.notify(
        category="info", payload_key=f"agent_failed:{run_id}", message=msg, ticket_id=ticket_id
    )


async def lifecycle(
    db: Database, *, run_id: int, signal: str
) -> dict:
    """lifecycle 신호. crash → failed. finish/running → status 반영."""
    if signal not in LIFECYCLE:
        raise AgentError(f"signal must be one of {sorted(LIFECYCLE)}")
    val = await db.fetchval(
        "UPDATE agent_runs SET status=$1, heartbeat_at=now() WHERE id=$2 RETURNING id",
        signal,
        run_id,
    )
    if val is None:
        raise AgentError(f"run {run_id} not found")
    return {"run_id": run_id, "status": signal}
