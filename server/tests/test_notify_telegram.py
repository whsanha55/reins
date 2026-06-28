# tests/test_notify_telegram.py — Telegram 발신(sendMessage 분할 + createForumTopic). MockTransport.
import httpx

from app.core.notify.notifier import NotifyMessage
from app.core.notify.telegram import TelegramNotifier


def _ok(result):
    return httpx.Response(200, json={"ok": True, "result": result})


def _transport(counts: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        counts["n"] += 1
        if "createForumTopic" in str(request.url):
            return _ok({"message_thread_id": 777})
        return _ok({"message_id": counts["n"]})

    return handler


async def test_send_single_message():
    counts = {"n": 0}
    client = httpx.AsyncClient(transport=httpx.MockTransport(_transport(counts)))
    n = TelegramNotifier("tok", client=client)
    await n.send("42", None, NotifyMessage("hello"))
    assert counts["n"] == 1
    await client.aclose()


async def test_send_splits_over_4096():
    counts = {"n": 0}
    client = httpx.AsyncClient(transport=httpx.MockTransport(_transport(counts)))
    n = TelegramNotifier("tok", client=client)
    await n.send("42", 5, NotifyMessage("a" * 5000))
    assert counts["n"] == 2  # 5000 → 2 chunks
    await client.aclose()


async def test_create_topic_returns_thread_id():
    counts = {"n": 0}
    client = httpx.AsyncClient(transport=httpx.MockTransport(_transport(counts)))
    n = TelegramNotifier("tok", client=client)
    tid = await n.create_topic("42", "결정필요")
    assert tid == 777
    assert n.create_topic_calls == 1
    await client.aclose()
