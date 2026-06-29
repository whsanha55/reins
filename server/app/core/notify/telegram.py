# core/notify/telegram.py — Telegram Bot API 발신(outbound-only — D5).
# sendMessage(message_thread_id=topic_id) + createForumTopic. 4096 분할.
# httpx client 는 테스트 주입 가능(transport mock). 미주입 시 단발 생성.
from __future__ import annotations

import logging

import httpx

from app.core.notify.notifier import Notifier, NotifyMessage

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 10.0
_MAX_TEXT = 4096  # Telegram sendMessage 한도. 초과 시 분할.


class TelegramNotifier(Notifier):
    channel = "telegram"

    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._client = client  # None → send/create_topic 내부 단발 생성. 테스트는 mock 주입.
        # ponytail: createForumTopic 호출 카운트 — QA/테스트가 "topic 재사용(2회째 미호출)" 검증.
        self.create_topic_calls = 0

    async def send(self, chat_id: str, topic_id: int | None, message: NotifyMessage) -> None:
        chunks = _split(message.text, _MAX_TEXT)
        for i, chunk in enumerate(chunks):
            payload: dict[str, object] = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
            }
            if topic_id is not None:
                payload["message_thread_id"] = topic_id
            # 인라인 키보드는 첫 chunk에만(카드는 보통 1메시지).
            if i == 0 and message.reply_markup:
                payload["reply_markup"] = message.reply_markup
            await self._post("sendMessage", payload)

    async def create_topic(self, chat_id: str, name: str) -> int:
        self.create_topic_calls += 1
        data = await self._post("createForumTopic", {"chat_id": chat_id, "name": name})
        return int(data["result"]["message_thread_id"])

    async def _post(self, method: str, payload: dict[str, object]) -> dict:
        url = _API_BASE.format(token=self._token, method=method)
        owns = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            resp = await client.post(url, json=payload, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        finally:
            if owns:
                await client.aclose()


def _split(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]
