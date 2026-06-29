# tests/test_telegram_webhook.py — 텔레그램 webhook 수신 → decision resolve 자동화.
# 인라인 키보드 콜백 파싱, secret/화이트리스트, reply_markup 발신 전달.
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.api.telegram import webhook
from app.config import settings
from app.core.notify.notifier import NotifyMessage
from app.core.notify.telegram import TelegramNotifier
from app.core.notify.topic_parser import resolve_keyboard


def _pending_decision(did: int = 5) -> dict:
    return {
        "id": did, "ticket_id": 1, "gate": "merge", "summary": "머지 결정",
        "status": "pending", "resolution_note": None,
    }


async def test_callback_resolves_approved():
    db = AsyncMock()
    db.fetchrow.return_value = _pending_decision()
    db.fetchval.return_value = 5  # UPDATE...RETURNING → applied
    disp = AsyncMock()
    payload = {"callback_query": {"id": "cb1", "from": {"id": 123}, "data": "resolve:5:approved"}}
    res = await webhook(payload, secret="", db=db, dispatcher=disp)
    assert res["ok"] is True
    assert res["applied"] is True
    assert res["status"] == "approved"


async def test_callback_rejected_resolution():
    db = AsyncMock()
    db.fetchrow.return_value = _pending_decision()
    db.fetchval.return_value = 5
    res = await webhook(
        {"callback_query": {"id": "c", "from": {"id": 1}, "data": "resolve:5:rejected"}},
        secret="", db=db, dispatcher=AsyncMock(),
    )
    assert res["ok"] and res["status"] == "rejected"


async def test_already_resolved_is_idempotent():
    db = AsyncMock()
    db.fetchrow.return_value = _pending_decision()
    db.fetchval.return_value = None  # UPDATE 매치 없음 → applied=False(중복)
    res = await webhook(
        {"callback_query": {"id": "c", "from": {"id": 1}, "data": "resolve:5:approved"}},
        secret="", db=db, dispatcher=AsyncMock(),
    )
    assert res["ok"] is True
    assert res["applied"] is False


async def test_bad_callback_format():
    res = await webhook(
        {"callback_query": {"id": "c", "from": {"id": 1}, "data": "resolve:nope:approved"}},
        secret="", db=AsyncMock(), dispatcher=AsyncMock(),
    )
    assert res["ok"] is False


async def test_secret_mismatch_401(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
    with pytest.raises(HTTPException) as exc:
        await webhook({}, secret="wrong", db=AsyncMock(), dispatcher=AsyncMock())
    assert exc.value.status_code == 401


async def test_whitelist_blocks_stranger(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", "123,456")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")  # _answer 스킵
    res = await webhook(
        {"callback_query": {"id": "c", "from": {"id": 999}, "data": "resolve:5:approved"}},
        secret="", db=AsyncMock(), dispatcher=AsyncMock(),
    )
    assert res["ok"] is False  # 999 미허가


async def test_non_callback_event_ignored():
    res = await webhook({"message": {"text": "hi"}}, secret="", db=AsyncMock(), dispatcher=AsyncMock())
    assert res["ok"] is True


def test_resolve_keyboard_structure():
    kb = resolve_keyboard(42)
    buttons = kb["inline_keyboard"][0]
    assert len(buttons) == 3
    assert buttons[0]["callback_data"] == "resolve:42:approved"
    assert buttons[2]["callback_data"] == "resolve:42:changes"


async def test_send_includes_reply_markup():
    captured = []

    def handler(req: httpx.Request) -> httpx.Response:
        import json
        captured.append(json.loads(req.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    n = TelegramNotifier("tok", client=client)
    await n.send(
        "42", None,
        NotifyMessage("card", reply_markup=resolve_keyboard(7)),
    )
    assert "reply_markup" in captured[0]
    assert captured[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "resolve:7:approved"
    await client.aclose()
