# core/notify/notifier.py — 발신 채널 추상. 신규 채널 = Notifier 구현 클래스 1개.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotifyMessage:
    """발신 단위. text 는 Telegram HTML (parse_mode=HTML). 동적값은 발신 전 escape_html 필수."""

    text: str
    # 인라인 키보드(선택). Telegram reply_markup. 결정 카드의 ✅/❌ 버튼 등.
    reply_markup: dict | None = None


class Notifier(ABC):
    channel: str = "base"

    @abstractmethod
    async def send(self, chat_id: str, topic_id: int | None, message: NotifyMessage) -> None:
        """chat_id 의 topic_id(포럼 토픽, None=일반) 로 전송."""

    @abstractmethod
    async def create_topic(self, chat_id: str, name: str) -> int:
        """새 포럼 토픽 생성 → message_thread_id."""
