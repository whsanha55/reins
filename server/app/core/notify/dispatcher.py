# core/notify/dispatcher.py — 발신 진입점.
# token 미설정 → 스킵. router 실패 → event log 폴백(P1, CRITICAL GAP).
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.core.notify.notifier import NotifyMessage
from app.core.notify.provisioner import AutoTopicProvisioner
from app.core.notify.router import NotifyRouter

if TYPE_CHECKING:
    from app.core.database import Database

logger = logging.getLogger(__name__)


class NotifyDispatcher:
    def __init__(
        self,
        db: Database,
        router: NotifyRouter | None = None,
        provisioner: AutoTopicProvisioner | None = None,
    ) -> None:
        self.db = db
        self._router = router or NotifyRouter(db)
        self._provisioner = provisioner or AutoTopicProvisioner(db)

    async def notify(
        self,
        *,
        category: str,
        payload_key: str,
        message: NotifyMessage,
        ticket_id: int | None = None,
    ) -> None:
        # token 미설정 → 스킵(로컬/CI). 운영에선 .env 필수.
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.info("TELEGRAM_BOT_TOKEN unset — notify skip (category=%s)", category)
            return
        try:
            await self._provisioner.ensure_route(category)
            await self._router.dispatch(category, payload_key, message)
        except Exception as e:
            # CRITICAL GAP: Telegram 다운 → 웹 타임라인에라도 보여야.
            await self._fallback(category, payload_key, str(e), ticket_id)

    async def _fallback(
        self, category: str, payload_key: str, error: str, ticket_id: int | None
    ) -> None:
        logger.error(
            "notify fallback category=%s payload_key=%s err=%s", category, payload_key, error
        )
        payload = json.dumps(
            {"category": category, "payload_key": payload_key, "error": error},
            ensure_ascii=False,
        )
        try:
            if ticket_id is not None:
                await self.db.execute(
                    "INSERT INTO ticket_events (ticket_id, kind, payload) "
                    "VALUES ($1, 'notify_failed', $2::jsonb)",
                    ticket_id,
                    payload,
                )
        except Exception as e:
            logger.error("notify fallback event write failed: %s", e)
