# tests/test_deploy.py — deploy_jobs 큐 lifecycle. 생성/클레임/회신(idempotent)/stale 정리.
# Atomic claim·idempotent finish 는 SQL 자체에 의존 → 호출되는 SQL 문 단언.
from unittest.mock import AsyncMock

from app.deploy.service import claim_job, create_job, finish_job, list_jobs, reset_stale_jobs


async def test_create_job_inserts_pending():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "project_id": 7, "ref": "main", "status": "pending"}
    job = await create_job(db, project_id=7, ref="main")
    assert job["id"] == 1
    assert job["status"] == "pending"
    assert "INSERT INTO deploy_jobs" in db.fetchrow.await_args.args[0]


async def test_claim_returns_none_when_empty():
    db = AsyncMock()
    db.fetchrow.return_value = None
    assert await claim_job(db) is None


async def test_claim_returns_running_job_with_skip_locked():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 9, "status": "running", "project_id": 7}
    job = await claim_job(db)
    assert job["id"] == 9
    sql = db.fetchrow.await_args.args[0]
    assert "FOR UPDATE SKIP LOCKED" in sql  # 다중 agent race 방지
    assert "status='running'" in sql


async def test_finish_applies_when_running():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 9, "status": "success", "exit_code": 0}
    r = await finish_job(db, job_id=9, status="success", exit_code=0, log_tail="ok")
    assert r["status"] == "success"
    assert "status='running'" in db.fetchrow.await_args.args[0]  # idempotent 가드


async def test_finish_idempotent_when_already_done():
    db = AsyncMock()
    db.fetchrow.return_value = None  # 이미 running 아님 → 미적용
    r = await finish_job(db, job_id=9, status="success", exit_code=0, log_tail="ok")
    assert r is None


async def test_reset_stale_counts_rows():
    db = AsyncMock()
    db.execute.return_value = "UPDATE 2"
    assert await reset_stale_jobs(db) == 2
    assert "status='running'" in db.execute.await_args.args[0]


async def test_list_jobs_joins_project_name():
    db = AsyncMock()
    db.fetch.return_value = [{"id": 1, "project_name": "reins"}]
    rows = await list_jobs(db, limit=10)
    assert rows[0]["project_name"] == "reins"
    assert "JOIN projects" in db.fetch.await_args.args[0]
