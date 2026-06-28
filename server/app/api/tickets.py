# api/tickets.py — 티켓 CRUD + 전이(상태기계) + reopen + 타임라인 이벤트.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.token import require_token
from app.deps import get_db, get_dispatcher
from app.ticket.service import (
    TicketError,
    create_ticket,
    get_ticket,
    list_events,
    list_tickets,
    record_event,
    reopen_ticket,
    transition_ticket,
    update_ticket,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"], dependencies=[Depends(require_token)])


class TicketIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    type: str = Field(default="task", pattern="^(task|epic)$")
    parent_id: int | None = None
    priority: int = 0


class TicketPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = None
    parent_id: int | None = None


class TransitionIn(BaseModel):
    to: str
    note: str | None = None


@router.get("")
async def get_tickets(
    db=Depends(get_db),
    project_id: int | None = None,
    status_: str | None = Query(default=None, alias="status"),
    parent_id: int | None = None,
    type: str | None = None,
    sort: str = Query(default="created", pattern="^(created|updated|priority)$"),
):
    return await list_tickets(
        db, project_id=project_id, status=status_, parent_id=parent_id, type=type, sort=sort
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_ticket(body: TicketIn, db=Depends(get_db)):
    return await create_ticket(
        db,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        type=body.type,
        parent_id=body.parent_id,
        priority=body.priority,
    )


@router.get("/{tid}")
async def get_one(tid: int, db=Depends(get_db)):
    t = await get_ticket(db, tid)
    if not t:
        raise HTTPException(404, "ticket not found")
    return t


@router.patch("/{tid}")
async def patch_one(tid: int, body: TicketPatch, db=Depends(get_db)):
    t = await update_ticket(
        db, tid, title=body.title, description=body.description,
        priority=body.priority, parent_id=body.parent_id,
    )
    if not t:
        raise HTTPException(404, "ticket not found")
    return t


@router.post("/{tid}/transition")
async def post_transition(
    tid: int, body: TransitionIn, db=Depends(get_db), dispatcher=Depends(get_dispatcher)
):
    try:
        return await transition_ticket(
            db, dispatcher, ticket_id=tid, to=body.to, note=body.note
        )
    except TicketError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{tid}/reopen")
async def post_reopen(tid: int, db=Depends(get_db), dispatcher=Depends(get_dispatcher)):
    try:
        return await reopen_ticket(db, dispatcher, ticket_id=tid)
    except TicketError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{tid}/cancel")
async def post_cancel(tid: int, db=Depends(get_db), dispatcher=Depends(get_dispatcher)):
    try:
        return await transition_ticket(
            db, dispatcher, ticket_id=tid, to="cancel", actor="user"
        )
    except TicketError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{tid}/events")
async def get_events(
    tid: int,
    db=Depends(get_db),
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_events(db, ticket_id=tid, cursor=cursor, limit=limit)


@router.post("/{tid}/note", status_code=status.HTTP_201_CREATED)
async def post_note(tid: int, body: TransitionIn, db=Depends(get_db)):
    """수동 메모 이벤트(타임라인 기록용)."""
    eid = await record_event(db, tid, "note", {"text": body.to})
    return {"id": eid}
