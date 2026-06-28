# core/notify/router.py — (category) → route 조회 + topic 재사용/자동생성 + notify_log 중복방지.
# 핵심 정책: topic_id 있으면 재사용, 없고 topic_name 있으면 createForumTopic → notify_routes 반영.
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.core.notify.notifier import Notifier
from app.core.notify.telegram import TelegramNotifier

if TYPE_CHECKING:
    from app.core.database import Database
    from app.core.notify.notifier import NotifyMessage

logger = logging.getLogger(__name__)


def _new_notifier(channel: str) -> Notifier:
    if channel == "telegram":
        return TelegramNotifier(settings.TELEGRAM_BOT_TOKEN)
    raise ValueError(f"unsupported notify channel: {channel!r}")


class NotifyRouter:
    def __init__(
        self,
        db: Database,
        notifier_override: dict[str, Notifier] | None = None,
    ) -> None:
        self.db = db
        # 테스트용 주입: {channel: Notifier(mock)}. None 이면 _new_notifier 로 생성.
        self._override = notifier_override

    async def dispatch(
        self, category: str, payload_key: str, message: NotifyMessage
    ) -> None:
        routes = await self._lookup(category)
        if not routes:
            logger.info("no notify route for category=%s — skip", category)
            return
        for route in routes:
            await self._send_one(route, payload_key, message)

    async def _lookup(self, category: str) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT id, channel, chat_id, topic_id, topic_name "
            "FROM notify_routes "
            "WHERE enabled AND (category=$1 OR category='') "
            "ORDER BY (category<>'') DESC",
            category,
        )
        return [dict(r) for r in rows]

    async def _send_one(
        self, route: dict, payload_key: str, message: NotifyMessage
    ) -> None:
        # 중복방지: 동일 (route_id, payload_key) 직전 success 있으면 스킵.
        if payload_key:
            sent = await self.db.fetchval(
                "SELECT 1 FROM notify_log "
                "WHERE route_id=$1 AND payload_key=$2 AND status='success'",
                route["id"],
                payload_key,
            )
            if sent:
                logger.info("dedup skip route=%s payload_key=%s", route["id"], payload_key)
                return

        notifier = self._notifier(route["channel"])
        topic_id = route["topic_id"]

        # topic 재사용/자동생성: topic_id 부재 + topic_name 있으면 1회 createForumTopic → 저장.
        if topic_id is None and route["topic_name"]:
            try:
                topic_id = await notifier.create_topic(route["chat_id"], route["topic_name"])
                await self.db.execute(
                    "UPDATE notify_routes SET topic_id=$1, updated_at=now() WHERE id=$2",
                    topic_id,
                    route["id"],
                )
            except Exception as e:
                logger.warning("create_topic failed (route %s): %s", route["id"], e)
                await self._log(route["id"], payload_key, "error", f"create_topic: {e}")
                return

        try:
            await notifier.send(route["chat_id"], topic_id, message)
            await self._log(route["id"], payload_key, "success")
        except Exception as e:
            logger.warning("notify send failed (route %s): %s", route["id"], e)
            await self._log(route["id"], payload_key, "error", str(e))
            raise

    def _notifier(self, channel: str) -> Notifier:
        if self._override and channel in self._override:
            return self._override[channel]
        return _new_notifier(channel)

    async def _log(
        self, route_id: int, payload_key: str, status: str, error: str | None = None
    ) -> None:
        try:
            await self.db.execute(
                "INSERT INTO notify_log (route_id, payload_key, status, error) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (route_id, payload_key) DO UPDATE "
                "SET status=EXCLUDED.status, error=EXCLUDED.error, sent_at=now()",
                route_id,
                payload_key,
                status,
                error,
            )
        except Exception as e:
            logger.error("notify_log write failed: %s", e)
