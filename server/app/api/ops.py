# api/ops.py — 아침 다이제스트 수동 실행 + 관측성 메트릭.
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.token import require_token
from app.core.notify.digest import build_and_dispatch
from app.deps import get_db, get_dispatcher

router = APIRouter(prefix="/api/ops", tags=["ops"], dependencies=[Depends(require_token)])


@router.post("/digest")
async def run_digest(db=Depends(get_db), dispatcher=Depends(get_dispatcher)):
    """아침 다이제스트 수동 트리거(LLM 無 집계 → telegram). 야간배치는 launchd 가 본 엔드포인트 호출."""
    return await build_and_dispatch(db, dispatcher)


@router.get("/metrics")
async def metrics(db=Depends(get_db)):
    """관측성 카운트(Section 8)."""
    by_status = {
        r["status"]: r["n"]
        for r in [
            dict(x) for x in await db.fetch(
                "SELECT status, count(*)::int AS n FROM tickets GROUP BY status"
            )
        ]
    }
    runs = {
        r["status"]: r["n"]
        for r in [
            dict(x) for x in await db.fetch(
                "SELECT status, count(*)::int AS n FROM agent_runs GROUP BY status"
            )
        ]
    }
    pending = await db.fetchval("SELECT count(*) FROM decisions WHERE status='pending'")
    return {"tickets_by_status": by_status, "agent_runs": runs, "decisions_pending": pending}
