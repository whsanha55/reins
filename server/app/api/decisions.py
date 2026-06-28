# api/decisions.py — 결정 큐. list / request(에이전트) / resolve(웹, idempotent).
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.token import require_token
from app.decision.service import DecisionError, list_decisions, request_decision, resolve
from app.deps import get_db, get_dispatcher

router = APIRouter(prefix="/api/decisions", tags=["decisions"], dependencies=[Depends(require_token)])


class DecisionIn(BaseModel):
    ticket_id: int
    gate: str = Field(pattern="^(pr_open|merge|deploy|spec_ambiguous)$")
    summary: str = Field(min_length=1, max_length=1000)
    agent_run_id: int | None = None


class ResolveIn(BaseModel):
    resolution: str = Field(pattern="^(approved|rejected|changes)$")
    note: str | None = None


@router.get("")
async def get_decisions(
    db=Depends(get_db),
    status_: str | None = Query(default=None, alias="status"),
):
    return await list_decisions(db, status_)


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_decision(body: DecisionIn, db=Depends(get_db), dispatcher=Depends(get_dispatcher)):
    return await request_decision(
        db,
        dispatcher,
        ticket_id=body.ticket_id,
        gate=body.gate,
        summary=body.summary,
        agent_run_id=body.agent_run_id,
    )


@router.post("/{did}/resolve")
async def post_resolve(
    did: int, body: ResolveIn, db=Depends(get_db), dispatcher=Depends(get_dispatcher)
):
    """idempotent: 더블클릭/중복 resolve → applied=False, 현재 상태 반환(200)."""
    try:
        return await resolve(
            db, dispatcher, decision_id=did, resolution=body.resolution, note=body.note
        )
    except DecisionError as e:
        raise HTTPException(400, str(e)) from e
