# api/deploy.py — 보드에서 배포(deploy 액션).
# UI: POST /projects/{pid}/deploy(트리거) · GET /deploy(이력) · GET /deploy/{jid}(상세).
# Agent: POST /deploy/reclaim-stale(기동) · POST /deploy/claim(클레임) · POST /deploy/{jid}/result(회신).
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.auth.token import require_token
from app.deps import get_db
from app.deploy.service import (
    claim_job,
    create_job,
    finish_job,
    get_job,
    list_jobs,
    reset_stale_jobs,
)

router = APIRouter(prefix="/api", tags=["deploy"], dependencies=[Depends(require_token)])

# branch/ref 만 허용 — shell 메타문자 차단(agent 가 git 인자로 사용).
_REF = r"^[A-Za-z0-9._/-]{1,120}$"


class DeployTriggerIn(BaseModel):
    ref: str = Field(default="main", pattern=_REF)


class DeployResultIn(BaseModel):
    status: str = Field(pattern="^(success|failed)$")
    exit_code: int
    log_tail: str | None = None


# ── UI 엔드포인트 ────────────────────────────────────────────

@router.post("/projects/{pid}/deploy", status_code=status.HTTP_201_CREATED)
async def trigger_deploy(pid: int, body: DeployTriggerIn, db=Depends(get_db)):
    project = await db.fetchrow("SELECT id, host_path FROM projects WHERE id=$1", pid)
    if not project:
        raise HTTPException(404, "project not found")
    if not project["host_path"]:
        raise HTTPException(400, "project has no host_path — deploy disabled")
    return await create_job(db, project_id=pid, ref=body.ref)


@router.get("/deploy")
async def list_deploy(
    db=Depends(get_db),
    project_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_jobs(db, project_id=project_id, limit=limit)


@router.get("/deploy/{jid}")
async def get_deploy(jid: int, db=Depends(get_db)):
    job = await get_job(db, jid)
    if not job:
        raise HTTPException(404, "deploy job not found")
    return job


# ── Agent 엔드포인트 (claim/result 는 {jid} int 경로보다 먼저 등록) ──

@router.post("/deploy/reclaim-stale")
async def reclaim_stale(db=Depends(get_db)):
    """agent 기동 시 1회: 크래시 잔재 stuck running → failed."""
    return {"reclaimed": await reset_stale_jobs(db)}


@router.post("/deploy/claim")
async def claim_deploy(db=Depends(get_db)):
    """가장 오래된 pending 클레임 → running. job + host_path 반환. 대기 없으면 204."""
    job = await claim_job(db)
    if not job:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    project = await db.fetchrow("SELECT host_path FROM projects WHERE id=$1", job["project_id"])
    return {**job, "host_path": project["host_path"] if project else None}


@router.post("/deploy/{jid}/result")
async def post_result(jid: int, body: DeployResultIn, db=Depends(get_db)):
    """agent 실행 결과 회신. idempotent: 이미 종료된 job 은 applied=False."""
    updated = await finish_job(
        db, job_id=jid, status=body.status, exit_code=body.exit_code, log_tail=body.log_tail
    )
    if updated:
        return {"applied": True, "job": updated}
    existing = await get_job(db, jid)
    if not existing:
        raise HTTPException(404, "deploy job not found")
    return {"applied": False, "job": existing}
