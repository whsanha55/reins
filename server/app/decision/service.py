# decision/service.py — 결정 큐. 요청(에이전트) + idempotent resolve(웹).
# CRITICAL GAP: 중복 resolve 1회만 적용(UPDATE...WHERE status='pending' RETURNING).
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import GATE_LABEL, classify, render_card, resolve_keyboard
from app.decision.github_merge import MergeError, extract_pr_number, merge_pr_github
from app.deploy.service import create_job
from app.ticket.service import record_event, transition_ticket

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
        # gate merge/deploy 승인 → PR 머지(merge만) + deploy job + ticket done 자동화.
        if resolution == "approved" and row["gate"] in ("merge", "deploy"):
            await _apply_approved_automation(db, dispatcher, decision=row, note=note)
    return {
        "id": decision_id,
        "applied": applied,
        "status": resolution,
        "previous_status": row["status"],
    }


async def _latest_diff_url(db: Database, ticket_id: int) -> str | None:
    """ticket_events 에서 가장 최근 kind='diff' 의 payload.url (PR URL)."""
    row = await db.fetchrow(
        "SELECT payload FROM ticket_events WHERE ticket_id=$1 AND kind='diff' "
        "ORDER BY id DESC LIMIT 1",
        ticket_id,
    )
    if not row:
        return None
    payload = row.get("payload") or {}
    return payload.get("url") if isinstance(payload, dict) else None


async def _automation_failed(
    db: Database,
    dispatcher: NotifyDispatcher,
    ticket_id: int,
    gate: str,
    reason: str,
) -> None:
    """머지 자동화 실패 → ticket progressing 유지(전이 X) + 이벤트 + 텔레그램 알림."""
    await record_event(db, ticket_id, "automation_failed", {"gate": gate, "reason": reason})
    msg = NotifyMessage(
        render_card(
            title=f"티켓 #{ticket_id} 자동화 실패 ({gate})",
            body=reason,
            category="info",
        )
    )
    await dispatcher.notify(
        category="info",
        payload_key=f"automation_failed:{ticket_id}:{gate}",
        message=msg,
        ticket_id=ticket_id,
    )


async def _apply_approved_automation(
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    decision: dict,
    note: str | None,
) -> None:
    """gate merge/deploy approved 부작용. 머지 실패 시 progressing 유지(early return).
    머지 성공 → deploy job(ref=main, merge-auto) + ticket done. deploy 게이트는 머지 생략."""
    ticket_id = decision["ticket_id"]
    gate = decision["gate"]
    project_id = await db.fetchval("SELECT project_id FROM tickets WHERE id=$1", ticket_id)

    if gate == "merge":
        diff_url = await _latest_diff_url(db, ticket_id)
        pr = extract_pr_number(diff_url)
        if pr is None:
            await _automation_failed(db, dispatcher, ticket_id, gate, f"PR 번호 추출 실패: {diff_url}")
            return
        try:
            res = await merge_pr_github(pr_number=pr, commit_title=f"#{ticket_id} auto-merge")
        except MergeError as e:
            await _automation_failed(db, dispatcher, ticket_id, gate, f"머지 실패: {e}")
            return
        await record_event(
            db,
            ticket_id,
            "pr_merged",
            {"pr": pr, "sha": res.get("sha"), "decision_id": decision["id"]},
        )
        await create_job(db, project_id=project_id, ref="main", triggered_by="merge-auto")
    elif gate == "deploy":
        await create_job(db, project_id=project_id, ref="main", triggered_by="merge-auto")

    await transition_ticket(
        db,
        dispatcher,
        ticket_id=ticket_id,
        to="done",
        actor="merge-bot",
        note=f"gate={gate} approved 자동화 완료",
    )
