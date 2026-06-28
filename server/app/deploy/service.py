# deploy/service.py — deploy_jobs 큐 DB 연산.
# reins API = 생성(트리거)/조회. jjong host agent = claim → 실행(git+deploy.sh) → result.
# 책임 분리(model 2): agent=공통 git 동기화, 각 repo deploy.sh=빌드. 본 모듈은 큐 상태만.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.database import Database


async def create_job(
    db: "Database", *, project_id: int, ref: str = "main", triggered_by: str = "manual"
) -> dict:
    """배포 트리거 → pending job 생성. host_path 검증은 라우터."""
    row = await db.fetchrow(
        "INSERT INTO deploy_jobs (project_id, ref, triggered_by) VALUES ($1, $2, $3) RETURNING *",
        project_id,
        ref,
        triggered_by,
    )
    return dict(row)


async def list_jobs(
    db: "Database", *, project_id: int | None = None, limit: int = 50
) -> list[dict]:
    args: list = []
    where = "TRUE"
    if project_id is not None:
        args.append(project_id)
        where = f"j.project_id=${len(args)}"
    args.append(limit)
    rows = await db.fetch(
        "SELECT j.*, p.name AS project_name "
        "FROM deploy_jobs j JOIN projects p ON p.id=j.project_id "
        f"WHERE {where} ORDER BY j.created_at DESC LIMIT ${len(args)}",
        *args,
    )
    return [dict(r) for r in rows]


async def get_job(db: "Database", job_id: int) -> dict | None:
    row = await db.fetchrow(
        "SELECT j.*, p.name AS project_name "
        "FROM deploy_jobs j JOIN projects p ON p.id=j.project_id WHERE j.id=$1",
        job_id,
    )
    return dict(row) if row else None


async def claim_job(db: "Database") -> dict | None:
    """가장 오래된 pending 1개 원자적 클레임(running 전이). 없으면 None.
    단일 UPDATE...RETURNING + CTE FOR UPDATE SKIP LOCKED → 다중 agent 환경에서도 race 없음."""
    row = await db.fetchrow(
        "UPDATE deploy_jobs SET status='running', started_at=now() WHERE id = "
        "(SELECT id FROM deploy_jobs WHERE status='pending' "
        "ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *"
    )
    return dict(row) if row else None


async def finish_job(
    db: "Database", *, job_id: int, status: str, exit_code: int, log_tail: str | None
) -> dict | None:
    """agent 결과 회신. status=success|failed. idempotent: 종료된 job 은 미적용(None)."""
    row = await db.fetchrow(
        "UPDATE deploy_jobs SET status=$2, exit_code=$3, log_tail=$4, finished_at=now() "
        "WHERE id=$1 AND status='running' RETURNING *",
        job_id,
        status,
        exit_code,
        log_tail,
    )
    return dict(row) if row else None


async def reset_stale_jobs(db: "Database") -> int:
    """크래시한 agent 가 남긴 stuck running job(10분 초과) → failed.
    agent 기동 시 1회 호출. 반환=영향받은 row 수."""
    result = await db.execute(
        "UPDATE deploy_jobs SET status='failed', finished_at=now(), "
        "log_tail=COALESCE(log_tail,'') || E'\\n[reins] agent 미회신(stale) → failed' "
        "WHERE status='running' AND started_at < now() - interval '600 seconds'"
    )
    return int(result.split()[-1]) if result else 0
