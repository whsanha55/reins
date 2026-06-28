# tests/test_decisions.py — 결정 resolve idempotency(CRITICAL GAP). 중복 resolve 1회만 적용.
from unittest.mock import AsyncMock

from app.decision.service import resolve


def _row():
    return {"id": 5, "ticket_id": 1, "gate": "merge", "status": "pending"}


async def test_resolve_applies_once():
    db = AsyncMock()
    db.fetchrow.return_value = _row()
    # 첫 resolve: UPDATE...WHERE pending RETURNING id → 적용.
    db.fetchval.return_value = 5
    r1 = await resolve(db, AsyncMock(), decision_id=5, resolution="approved", note="go")
    assert r1["applied"] is True

    # 두 번째(더블클릭): 동일 decision 은 이미 pending 아님 → RETURNING None → applied False.
    db.fetchrow.return_value = {**_row(), "status": "approved"}
    db.fetchval.return_value = None
    r2 = await resolve(db, AsyncMock(), decision_id=5, resolution="approved", note="go")
    assert r2["applied"] is False  # idempotent: 에러 아님, 2회째 미적용


async def test_resolve_records_event_when_applied():
    db = AsyncMock()
    db.fetchrow.return_value = _row()
    db.fetchval.return_value = 5
    dispatcher = AsyncMock()
    await resolve(db, dispatcher, decision_id=5, resolution="rejected", note="no")
    # record_event 가 INSERT ticket_events 호출.
    assert any("ticket_events" in c.args[0] for c in db.fetchval.await_args_list)
