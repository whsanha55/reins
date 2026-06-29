# ticket/service.py — 티켓 DB 연산 + 전이(상태기계) + 이벤트 기록 + 정보성 notify.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.notify.notifier import NotifyMessage
from app.core.notify.topic_parser import render_card
from app.ticket.state import can_transition

if TYPE_CHECKING:
    from app.core.database import Database
    from app.core.notify.dispatcher import NotifyDispatcher

_SORT = {
    "created": "created_at ASC",
    "updated": "updated_at DESC",
    "priority": "priority DESC, created_at ASC",
}


class TicketError(ValueError):
    pass


async def record_event(db: Database, ticket_id: int, kind: str, payload: dict) -> int:
    """append-only 이벤트. 반환 = 새 event id(타임라인 커서용)."""
    return await db.fetchval(
        "INSERT INTO ticket_events (ticket_id, kind, payload) VALUES ($1, $2, $3::jsonb) "
        "RETURNING id",
        ticket_id,
        kind,
        json.dumps(payload, ensure_ascii=False),
    )


async def create_ticket(
    db: Database,
    *,
    project_id: int,
    title: str,
    description: str | None = None,
    type: str = "task",
    parent_id: int | None = None,
    priority: int = 0,
) -> dict:
    row = await db.fetchrow(
        "INSERT INTO tickets (project_id, title, description, type, parent_id, priority, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, 'todo') RETURNING *",
        project_id,
        title,
        description,
        type,
        parent_id,
        priority,
    )
    d = dict(row)
    await record_event(db, d["id"], "created", {"title": title, "type": type})
    return d


async def get_ticket(db: Database, ticket_id: int) -> dict | None:
    row = await db.fetchrow("SELECT * FROM tickets WHERE id=$1", ticket_id)
    return dict(row) if row else None


async def list_tickets(
    db: Database,
    *,
    project_id: int | None = None,
    status: str | None = None,
    parent_id: int | None = None,
    type: str | None = None,
    sort: str = "created",
) -> list[dict]:
    order = _SORT.get(sort, _SORT["created"])
    where = ["TRUE"]
    args: list = []
    if project_id is not None:
        args.append(project_id)
        where.append(f"project_id=${len(args)}")
    if status is not None:
        args.append(status)
        where.append(f"status=${len(args)}")
    if parent_id is not None:
        args.append(parent_id)
        where.append(f"parent_id=${len(args)}")
    if type is not None:
        args.append(type)
        where.append(f"type=${len(args)}")
    rows = await db.fetch(
        f"SELECT * FROM tickets WHERE {' AND '.join(where)} ORDER BY {order}",
        *args,
    )
    return [dict(r) for r in rows]


async def update_ticket(
    db: Database, ticket_id: int, *, title: str | None = None, description: str | None = None,
    priority: int | None = None, parent_id: int | None = None,
) -> dict | None:
    sets = []
    args: list = []
    if title is not None:
        args.append(title)
        sets.append(f"title=${len(args)}")
    if description is not None:
        args.append(description)
        sets.append(f"description=${len(args)}")
    if priority is not None:
        args.append(priority)
        sets.append(f"priority=${len(args)}")
    if parent_id is not None:
        args.append(parent_id)
        sets.append(f"parent_id=${len(args)}")
    if not sets:
        return await get_ticket(db, ticket_id)
    sets.append("updated_at=now()")
    args.append(ticket_id)
    row = await db.fetchrow(
        f"UPDATE tickets SET {', '.join(sets)} WHERE id=${len(args)} RETURNING *",
        *args,
    )
    return dict(row) if row else None


async def transition_ticket(
    db: Database,
    dispatcher: NotifyDispatcher,
    *,
    ticket_id: int,
    to: str,
    actor: str = "user",
    note: str | None = None,
) -> dict:
    row = await db.fetchrow(
        "SELECT id, status, title, parent_id FROM tickets WHERE id=$1", ticket_id
    )
    if not row:
        raise TicketError(f"ticket {ticket_id} not found")
    frm = row["status"]
    if not can_transition(frm, to):
        raise TicketError(f"invalid transition {frm} -> {to}")
    await db.execute(
        "UPDATE tickets SET status=$1, updated_at=now() WHERE id=$2", to, ticket_id
    )
    await record_event(
        db, ticket_id, "transition", {"from": frm, "to": to, "actor": actor, "note": note}
    )
    # #18: done 전이만 알림. progressing/qa/cancel 전이는 알림 생략.
    if to == "done":
        body = f"{frm} → {to}" + (f"\n{note}" if note else "")
        msg = NotifyMessage(render_card(title=row["title"], body=body, category="info"))
        await dispatcher.notify(
            category="info",
            payload_key=f"transition:{ticket_id}:{frm}:{to}",
            message=msg,
            ticket_id=ticket_id,
        )
    # #21: 하위 티켓이 종료(done/cancel)되어 에픽의 모든 하위가 종료되면 에픽 자동 done.
    if to in ("done", "cancel") and row["parent_id"]:
        await _maybe_complete_epic(db, dispatcher, row["parent_id"])
    return {"id": ticket_id, "from": frm, "to": to}


async def _maybe_complete_epic(db: Database, dispatcher: NotifyDispatcher, epic_id: int) -> None:
    """에픽의 모든 하위가 done/cancel 이면 에픽을 자동 done. (#21) 하위 0개면 무동작."""
    epic = await db.fetchrow(
        "SELECT id, status, title FROM tickets WHERE id=$1 AND type='epic'", epic_id
    )
    if not epic or epic["status"] == "done":
        return
    children = await db.fetch("SELECT status FROM tickets WHERE parent_id=$1", epic_id)
    if not children or not all(c["status"] in ("done", "cancel") for c in children):
        return
    frm = epic["status"]
    await db.execute("UPDATE tickets SET status='done', updated_at=now() WHERE id=$1", epic_id)
    await record_event(
        db, epic_id, "transition",
        {"from": frm, "to": "done", "actor": "system", "note": "all children closed"},
    )
    # #18: done 알림.
    msg = NotifyMessage(
        render_card(title=epic["title"], body=f"{frm} → done (하위 전체 종료)", category="info")
    )
    await dispatcher.notify(
        category="info", payload_key=f"epic-auto-done:{epic_id}", message=msg, ticket_id=epic_id
    )


async def reopen_ticket(
    db: Database, dispatcher: NotifyDispatcher, *, ticket_id: int
) -> dict:
    # reopen 은 done|cancel → todo. 전이 화이트리스트 밖이라 직접 처리(명시적 엔드포인트).
    from app.ticket.state import can_reopen

    row = await db.fetchrow("SELECT id, status, title FROM tickets WHERE id=$1", ticket_id)
    if not row:
        raise TicketError(f"ticket {ticket_id} not found")
    if not can_reopen(row["status"]):
        raise TicketError(f"cannot reopen from {row['status']}")
    frm = row["status"]
    await db.execute(
        "UPDATE tickets SET status='todo', updated_at=now() WHERE id=$1", ticket_id
    )
    await record_event(db, ticket_id, "transition", {"from": frm, "to": "todo", "actor": "user"})
    # #18: done 전이만 알림 — reopen(→todo)은 생략.
    return {"id": ticket_id, "from": frm, "to": "todo"}


async def list_events(
    db: Database, *, ticket_id: int, cursor: int | None = None, limit: int = 50
) -> dict:
    """타임라인 이벤트. id 커서 페이지네이션(append-only, ASC)."""
    if cursor:
        rows = await db.fetch(
            "SELECT id, ticket_id, kind, payload, created_at FROM ticket_events "
            "WHERE ticket_id=$1 AND id > $2 ORDER BY id ASC LIMIT $3",
            ticket_id,
            cursor,
            limit,
        )
    else:
        rows = await db.fetch(
            "SELECT id, ticket_id, kind, payload, created_at FROM ticket_events "
            "WHERE ticket_id=$1 ORDER BY id ASC LIMIT $2",
            ticket_id,
            limit,
        )
    items = [dict(r) for r in rows]
    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}
