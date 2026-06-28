# api/agent.py — 로컬 에이전트 엔드포인트. 원자클레임/heartbeat/결과/lifecycle.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agent.service import AgentError, claim, heartbeat, lifecycle, submit_result
from app.auth.token import require_token
from app.deps import get_db, get_dispatcher

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(require_token)])


class ClaimIn(BaseModel):
    project_id: int | None = None


class ResultIn(BaseModel):
    # 서버 canonical 스키마(D6). 상세 검증은 validate_agent_result.
    status: str
    summary: str
    gate: str | None = None
    gate_summary: str | None = None
    diff_url: str | None = None
    events: list[dict] | None = None


class LifecycleIn(BaseModel):
    signal: str = Field(pattern="^(running|succeeded|failed|stalled)$")


@router.post("/claim")
async def post_claim(body: ClaimIn, db=Depends(get_db)):
    """원자적 클레임. todo 한 건 → progressing + run. 없으면 404(no work)."""
    res = await claim(db, project_id=body.project_id)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no ticket to claim")
    return res


@router.post("/runs/{run_id}/heartbeat")
async def post_heartbeat(run_id: int, db=Depends(get_db)):
    ok = await heartbeat(db, run_id)
    return {"run_id": run_id, "heartbeat": ok}


@router.post("/runs/{run_id}/result")
async def post_result(run_id: int, body: ResultIn, db=Depends(get_db), dispatcher=Depends(get_dispatcher)):
    try:
        return await submit_result(db, dispatcher, run_id=run_id, payload=body.model_dump())
    except AgentError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/runs/{run_id}/lifecycle")
async def post_lifecycle(run_id: int, body: LifecycleIn, db=Depends(get_db)):
    try:
        return await lifecycle(db, run_id=run_id, signal=body.signal)
    except AgentError as e:
        raise HTTPException(400, str(e)) from e
