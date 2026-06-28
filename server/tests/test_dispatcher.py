# tests/test_dispatcher.py — token 미설정 스킵 + 발신 실패 시 event log 폴백(CRITICAL GAP).
from unittest.mock import AsyncMock

from app.core.notify.dispatcher import NotifyDispatcher
from app.core.notify.notifier import NotifyMessage


async def test_skip_when_no_token(monkeypatch):
    monkeypatch.setattr("app.core.notify.dispatcher.settings.TELEGRAM_BOT_TOKEN", "")
    db = AsyncMock()
    d = NotifyDispatcher(db)
    await d.notify(category="info", payload_key="k", message=NotifyMessage("x"), ticket_id=1)
    db.execute.assert_not_awaited()  # 스킵


async def test_fallback_writes_event_on_failure(monkeypatch):
    monkeypatch.setattr("app.core.notify.dispatcher.settings.TELEGRAM_BOT_TOKEN", "tok")
    db = AsyncMock()
    d = NotifyDispatcher(db)
    # provisioner OK, router.dispatch 예외 → 폴백.
    d._provisioner.ensure_route = AsyncMock()
    d._router.dispatch = AsyncMock(side_effect=RuntimeError("boom"))
    await d.notify(category="info", payload_key="k", message=NotifyMessage("x"), ticket_id=7)
    # ticket_events 폴백 기록됨.
    assert db.execute.await_count == 1
    sql = db.execute.await_args.args[0]
    assert "notify_failed" in sql and "ticket_id" in sql
