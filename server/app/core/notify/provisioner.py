# core/notify/provisioner.py — AutoTopicProvisioner (lazy 자동생성).
# 매칭 route 無 → notify_routes INSERT (topic_name=label, topic_id=NULL).
# topic_id 채움은 router._send_one 담당(createForumTopic). reins 은 D5(서버 LLM 禁):
# scoophub 의 LLM 한국어 이름 생성 폴백은 제거 — topic_parser.CATEGORY_LABEL 사용.
# 사용: router.dispatch 직전 ensure_route(category) 1회(라우트 시드 누락 안전망).
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.core.notify.topic_parser import CATEGORY_LABEL

if TYPE_CHECKING:
    from app.core.database import Database

logger = logging.getLogger(__name__)


class AutoTopicProvisioner:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def ensure_route(self, category: str) -> None:
        # 폭증 가드: 기본 chat_id 미설정 → 자동생성 無.
        chat_id = settings.TELEGRAM_DEFAULT_CHAT_ID
        if not chat_id:
            return

        # 매칭 라우트 有 → 반환.
        if await self.db.fetchval(
            "SELECT 1 FROM notify_routes WHERE enabled AND (category=$1 OR category='') LIMIT 1",
            category,
        ):
            return

        label = CATEGORY_LABEL.get(category, category)
        await self.db.execute(
            "INSERT INTO notify_routes "
            "(category, channel, chat_id, topic_id, topic_name, enabled) "
            "VALUES ($1, 'telegram', $2, NULL, $3, TRUE) "
            "ON CONFLICT DO NOTHING",
            category,
            chat_id,
            label,
        )
        logger.info("provisioned notify route category=%s label=%s", category, label)
