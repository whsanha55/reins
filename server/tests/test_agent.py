# tests/test_agent.py — 원자클레임 흐름 + 결과 스키마 위반→카드정지(D7-B) + watchdog 정체.
from unittest.mock import AsyncMock

from app.agent.service import claim, submit_result
from app.agent.watchdog import sweep


async def test_claim_returns_ticket_and_run():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 9, "project_id": 1, "title": "t", "status": "progressing"}
    db.fetchval.return_value = 100  # run_id
    res = await claim(db, project_id=1)
    assert res["ticket"]["id"] == 9
    assert res["run_id"] == 100
    sql = db.fetchrow.await_args.args[0]
    assert "FOR UPDATE SKIP LOCKED" in sql  # 원자적 클레임


async def test_claim_none_when_no_work():
    db = AsyncMock()
    db.fetchrow.return_value = None
    assert await claim(db) is None


async def test_submit_result_malformed_fails_run_no_transition():
    """D7-B CRITICAL: malformed 결과 → run failed, 카드 이동 無."""
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "ticket_id": 7, "status": "running"}
    dispatcher = AsyncMock()
    # summary 빠진 malformed payload.
    out = await submit_result(db, dispatcher, run_id=1, payload={"status": "succeeded"})
    assert out["status"] == "failed"
    assert isinstance(out["reason"], str)
    # 전이 UPDATE(tickets status) 미호출 — 카드 정지.
    ticket_updates = [
        c for c in db.execute.await_args_list if "UPDATE tickets" in c.args[0]
    ]
    assert ticket_updates == []
    # run failed 처리는 호출됨.
    assert any("agent_runs SET status='failed'" in c.args[0] for c in db.execute.await_args_list)


async def test_submit_result_valid_with_gate_requests_decision():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "ticket_id": 7, "status": "running"}
    dispatcher = AsyncMock()
    out = await submit_result(
        db,
        dispatcher,
        run_id=1,
        payload={"status": "succeeded", "summary": "impl", "gate": "pr_open", "diff_url": "http://u/1"},
    )
    assert out["status"] == "succeeded" and out["gate"] == "pr_open"


async def test_watchdog_marks_stale_run_stalled():
    db = AsyncMock()
    db.fetch.return_value = [{"id": 50, "ticket_id": 7, "heartbeat_at": None}]
    dispatcher = AsyncMock()
    out = await sweep(db, dispatcher, stale_sec=1800)
    assert out == [{"run_id": 50, "ticket_id": 7}]
    # run stalled + 티켓 todo 복귀.
    assert any("status='stalled'" in c.args[0] for c in db.execute.await_args_list)
    assert any("status='todo'" in c.args[0] for c in db.execute.await_args_list)


async def test_watchdog_no_stale_is_noop():
    db = AsyncMock()
    db.fetch.return_value = []
    out = await sweep(db, AsyncMock(), stale_sec=1800)
    assert out == []
