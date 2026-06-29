# tests/test_ticket_notify.py — #18: done 전이만 알림. #21: 하위 전체 종료 시 에픽 자동 done.
# #29: 묶음 done 전이 → 1개 release 알림.
from unittest.mock import AsyncMock

import pytest

from app.ticket.service import (
    TicketError,
    reopen_ticket,
    transition_batch,
    transition_ticket,
)


async def test_notify_only_on_done():
    db = AsyncMock()
    db.fetchrow.return_value = {"id": 1, "status": "qa", "title": "t", "parent_id": None, "project_id": 1}
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
        db.fetchrow.return_value = {"id": 1, "status": frm, "title": "t", "parent_id": None, "project_id": 1}
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


async def test_epic_auto_done_when_all_children_closed():
    # 하위 done 전이 → 에픽 조회 → 모든 하위 done/cancel → 에픽 자동 done.
    db = AsyncMock()
    db.fetchrow.side_effect = [
        {"id": 2, "status": "qa", "title": "child", "parent_id": 10, "project_id": 1},  # 전이 대상(하위)
        {"id": 10, "status": "progressing", "title": "epic", "project_id": 1},          # 부모 에픽
    ]
    db.fetch.return_value = [{"status": "done"}, {"status": "cancel"}]
    db.fetchval.return_value = 1
    disp = AsyncMock()
    await transition_ticket(db, disp, ticket_id=2, to="done")
    assert disp.notify.await_count == 2  # 하위 done + 에픽 자동 done
    assert any("status='done'" in c.args[0] for c in db.execute.await_args_list)


async def test_epic_not_done_when_child_still_open():
    db = AsyncMock()
    db.fetchrow.side_effect = [
        {"id": 2, "status": "qa", "title": "child", "parent_id": 10, "project_id": 1},
        {"id": 10, "status": "progressing", "title": "epic", "project_id": 1},
    ]
    db.fetch.return_value = [{"status": "done"}, {"status": "progressing"}]  # 하나 미종료
    db.fetchval.return_value = 1
    disp = AsyncMock()
    await transition_ticket(db, disp, ticket_id=2, to="done")
    assert not any("status='done'" in c.args[0] for c in db.execute.await_args_list)


async def test_batch_done_single_release_notify():
    # #29: 3개 qa → done 묶음 전이 → 우루루 대신 알림 1회(release 카드, 3개 딥링크).
    db = AsyncMock()
    db.fetch.return_value = [
        {"id": 1, "status": "qa"}, {"id": 2, "status": "qa"}, {"id": 3, "status": "qa"}
    ]
    db.fetchrow.side_effect = [
        {"id": 1, "status": "qa", "title": "a", "parent_id": None, "project_id": 1},
        {"id": 2, "status": "qa", "title": "b", "parent_id": None, "project_id": 1},
        {"id": 3, "status": "qa", "title": "c", "parent_id": None, "project_id": 1},
    ]
    db.fetchval.return_value = 1
    disp = AsyncMock()
    res = await transition_batch(db, disp, ids=[1, 2, 3], to="done")
    assert disp.notify.await_count == 1  # N건 → 알림 1개
    text = str(disp.notify.await_args.kwargs["message"].text)
    assert "3건" in text
    assert all(f"/t/{tid}" in text for tid in (1, 2, 3))
    assert len(res["transitioned"]) == 3


async def test_batch_missing_id_aborts_before_mutation():
    # 존재하지 않는 id가 섞이면 사전검증에서 raise — 변경/알림 없음(부분반영 방지).
    db = AsyncMock()
    db.fetch.return_value = [{"id": 1, "status": "qa"}]  # id 2 없음
    disp = AsyncMock()
    with pytest.raises(TicketError):
        await transition_batch(db, disp, ids=[1, 2], to="done")
    db.execute.assert_not_awaited()
    disp.notify.assert_not_awaited()


async def test_batch_dedupes_ids():
    # 중복 id → 1회만 전이(재전이/중복 카드줄 방지).
    db = AsyncMock()
    db.fetch.return_value = [{"id": 1, "status": "qa"}]
    db.fetchrow.return_value = {
        "id": 1, "status": "qa", "title": "a", "parent_id": None, "project_id": 1
    }
    db.fetchval.return_value = 1
    disp = AsyncMock()
    res = await transition_batch(db, disp, ids=[1, 1], to="done")
    assert len(res["transitioned"]) == 1
    assert "1건" in str(disp.notify.await_args.kwargs["message"].text)


async def test_batch_cancel_epic_auto_done_notifies():
    # cancel 배치: release 카드 없음. 마지막 하위 cancel로 에픽 자동 done → 에픽 개별 알림(단일 경로 parity).
    db = AsyncMock()
    db.fetch.side_effect = [
        [{"id": 2, "status": "qa"}],   # 사전검증
        [{"status": "cancel"}],        # 에픽 children 전체 종료
    ]
    db.fetchrow.side_effect = [
        {"id": 2, "status": "qa", "title": "child", "parent_id": 10, "project_id": 1},
        {"id": 10, "status": "progressing", "title": "epic", "project_id": 1},
    ]
    db.fetchval.return_value = 1
    disp = AsyncMock()
    res = await transition_batch(db, disp, ids=[2], to="cancel")
    assert disp.notify.await_count == 1  # release 카드 X, 에픽 done 알림만
    text = str(disp.notify.await_args.kwargs["message"].text)
    assert "/t/10" in text and "하위 전체 종료" in text
    assert res["epics_done"] == [10]
