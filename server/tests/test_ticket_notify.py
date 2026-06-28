# tests/test_ticket_notify.py — #18: done 전이만 알림. progressing/qa/cancel/reopen 은 알림 생략.
from unittest.mock import AsyncMock

from app.ticket.service import reopen_ticket, transition_ticket


async def test_notify_only_on_done():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "status": "qa", "title": "t", "project_id": 1}
    db.fetchval.return_value = 1
    disp = AsyncMock()
    await transition_ticket(db, disp, ticket_id=1, to="done")
    assert disp.notify.await_count == 1  # qa → done : 알림 1회
    # #27: 알림 메시지에 티켓 딥링크 포함.
    msg = disp.notify.await_args.kwargs["message"]
    assert "/project/1/t/1" in str(msg.text if hasattr(msg, "text") else msg)


async def test_no_notify_on_non_done():
    disp = AsyncMock()
    for frm, to in (("todo", "progressing"), ("progressing", "qa"), ("progressing", "cancel")):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "status": frm, "title": "t", "project_id": 1}
        db.fetchval.return_value = 1
        await transition_ticket(db, disp, ticket_id=1, to=to)
    assert disp.notify.await_count == 0  # done 외 전이는 알림 없음


async def test_no_notify_on_reopen():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "status": "done", "title": "t"}
    db.fetchval.return_value = 1
    disp = AsyncMock()
    await reopen_ticket(db, disp, ticket_id=1)
    assert disp.notify.await_count == 0  # reopen(→todo)은 알림 없음
