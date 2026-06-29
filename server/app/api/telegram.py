# api/telegram.py — Telegram webhook 수신. 인라인 키보드 콜백 → decision resolve.
# 보안: secret 쿼리 + from.id 화이트리스트. require_token 제외(Telegram 서버 호출).
# setWebhook 등록(운영): POST bot{token}/setWebhook url=https://reins.gonamu.com/api/telegram/webhook?secret=X
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.core.database import Database
from app.core.notify.topic_parser import RESOLVE_CB_PREFIX
from app.decision.service import DecisionError, resolve
from app.deps import get_db, get_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def webhook(
    payload: dict,
    secret: str = Query(default=""),
    db: Database = Depends(get_db),
    dispatcher=Depends(get_dispatcher),
):
    # secret: 미설정(로컬) 시 스킵. 운영에선 setWebhook URL 에 secret 쿼리로 세팅.
    if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad secret")

    cb = payload.get("callback_query")
    if not cb:
        # callback 아닌 이벤트(일반 메시지 등)는 무시. 향후 명령어 처리 확장 지점.
        return {"ok": True}

    allowed = _allowed_ids()
    if allowed:
        from_id = cb.get("from", {}).get("id")
        if from_id not in allowed:
            await _answer(cb["id"], "⛔ 미허가 사용자")
            return {"ok": False}

    data = cb.get("data", "")
    if not data.startswith(RESOLVE_CB_PREFIX):
        await _answer(cb["id"])
        return {"ok": True}

    # resolve:{decision_id}:{resolution}
    parts = data.split(":")
    if len(parts) != 3:
        await _answer(cb["id"], "잘못된 콜백 형식")
        return {"ok": False}
    try:
        decision_id = int(parts[1])
        resolution = parts[2]
    except ValueError:
        await _answer(cb["id"], "잘못된 콜백")
        return {"ok": False}

    try:
        res = await resolve(db, dispatcher, decision_id=decision_id, resolution=resolution)
    except DecisionError as e:
        await _answer(cb["id"], f"오류: {e}")
        return {"ok": False, "error": str(e)}

    note = "적용됨" if res["applied"] else "이미 처리됨"
    await _answer(cb["id"], f"{resolution} — {note}")
    return {"ok": True, **res}


def _allowed_ids() -> set[int]:
    return {int(x) for x in settings.TELEGRAM_ALLOWED_CHAT_IDS.split(",") if x.strip()}


async def _answer(callback_query_id: str, text: str | None = None) -> None:
    """버튼 누름 스피너 종료 + 짧은 피드백. token 없으면 스킵."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    body: dict[str, object] = {"callback_query_id": callback_query_id}
    if text:
        body["text"] = text[:200]
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=body, timeout=10.0)
        except httpx.HTTPError:
            logger.warning("answerCallbackQuery failed — non-fatal")
