# tests/test_notify_router.py — router 핵심: 중복방지 + topic 자동생성(1회) + 재사용(2회째 미호출).
from unittest.mock import AsyncMock

import httpx

from app.core.notify.notifier import NotifyMessage
from app.core.notify.router import NotifyRouter
from app.core.notify.telegram import TelegramNotifier


def _ok(result):
    return httpx.Response(200, json={"ok": True, "result": result})


def _transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if "createForumTopic" in str(request.url):
            return _ok({"message_thread_id": 777})
        return _ok({"message_id": 1})

    return handler


def _make_notifier():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_transport()))
    return TelegramNotifier("tok", client=client), client


def _route(topic_id):
    return [{
        "id": 1, "channel": "telegram", "chat_id": "42",
        "topic_id": topic_id, "topic_name": "결정필요",
    }]


async def test_topic_autocreate_then_reuse():
    """★ 핵심 요청: 없으면 createForumTopic(1회), 있으면 topic_id 재사용(2회째 미호출)."""
    notifier, client = _make_notifier()
    db = AsyncMock()
    db.fetch.return_value = _route(None)  # 첫 발신: topic_id 미확정
    db.fetchval.return_value = None       # 중복 아님
    db.execute.return_value = ""
    router = NotifyRouter(db, notifier_override={"telegram": notifier})

    await router.dispatch("decision", "decision:1", NotifyMessage("<b>a</b>"))
    assert notifier.create_topic_calls == 1  # 최초 1회 createForumTopic

    # 두 번째: route 가 이제 topic_id 를 갖는다고 가정(직전 UPDATE 로 저장됨).
    db.fetch.return_value = _route(777)
    db.fetchval.return_value = None  # 다른 payload_key → 미중복
    await router.dispatch("decision", "decision:2", NotifyMessage("<b>b</b>"))
    assert notifier.create_topic_calls == 1  # 재사용 → 추가 createForumTopic 無
    await client.aclose()


async def test_dedup_skips_already_sent():
    notifier, client = _make_notifier()
    db = AsyncMock()
    db.fetch.return_value = _route(99)
    db.fetchval.return_value = 1  # 이미 success 전송됨 → 중복
    sends = {"n": 0}

    orig_send = notifier.send

    async def counting_send(*a, **k):
        sends["n"] += 1
        await orig_send(*a, **k)

    notifier.send = counting_send
    router = NotifyRouter(db, notifier_override={"telegram": notifier})
    await router.dispatch("decision", "decision:1", NotifyMessage("<b>x</b>"))
    assert sends["n"] == 0  # 중복 → 미발송
    await client.aclose()
