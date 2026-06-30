# tests/test_sprint_epics.py — #36: 스프린트 시작(종료) 시 미종료 에픽 자동 done.
# close_open_epics 가 미종료 에픽만 닫고 done/cancel 은 건드리지 않는지 검증.
# create_sprint API 가 close_open_epics → INSERT 순서로 호출하는지는 service 단위 테스트로 커버.
from unittest.mock import AsyncMock

from app.ticket.service import close_open_epics


async def test_close_open_epics_closes_only_non_terminal():
    # 미종료(todo/progressing/qa) 에픽만 done 으로 닫힌다. done/cancel 을 그대로.
    db = AsyncMock()
    db.fetch.return_value = [
        {"id": 10, "status": "todo", "title": "epic-a", "project_id": 1},
        {"id": 11, "status": "progressing", "title": "epic-b", "project_id": 1},
        {"id": 12, "status": "qa", "title": "epic-c", "project_id": 1},
    ]
    db.fetchval.return_value = 1  # record_event 가 반환하는 event id
    closed = await close_open_epics(db, project_id=1)
    assert len(closed) == 3
    closed_ids = {e["id"] for e in closed}
    assert closed_ids == {10, 11, 12}
    # 각 에픽마다 status='done' UPDATE 가 실행됨 (총 3회).
    done_updates = [c for c in db.execute.await_args_list if "status='done'" in c.args[0]]
    assert len(done_updates) == 3
    # 각 에픽마다 transition 이벤트 기록됨.
    assert db.fetchval.await_count == 3
    # 이벤트 note 가 "sprint ended". record_event 는 payload 를 json.dumps 한 문자열로 전달.
    import json as _json
    for call in db.fetchval.await_args_list:
        payload = _json.loads(call.args[3])
        assert payload["to"] == "done"
        assert payload["actor"] == "system"
        assert payload["note"] == "sprint ended"


async def test_close_open_epics_ignores_already_closed():
    # 이미 done/cancel 인 에픽은 SELECT 되지 않으므로(쿼리 WHERE) 닫지 않는다.
    db = AsyncMock()
    db.fetch.return_value = []  # 미종료 에픽 없음
    db.fetchval.return_value = 1
    closed = await close_open_epics(db, project_id=1)
    assert closed == []
    db.execute.assert_not_awaited()


async def test_close_open_epics_scoped_to_project():
    # project_id 인자가 쿼리에 전달된다 (다른 프로젝트 에픽 영향 X).
    db = AsyncMock()
    db.fetch.return_value = [
        {"id": 20, "status": "todo", "title": "only-this-project", "project_id": 7},
    ]
    db.fetchval.return_value = 1
    closed = await close_open_epics(db, project_id=7)
    assert len(closed) == 1
    # fetch 호출의 첫 인자(쿼리)와 두 번째 인자(project_id) 확인.
    fetch_call = db.fetch.await_args
    assert fetch_call.args[1] == 7
    # 반환값에 from 상태 포함.
    assert closed[0]["from"] == "todo"


async def test_close_open_epics_records_event_per_epic():
    # 닫힌 에픽마다 transition 이벤트가 별도로 기록됨.
    db = AsyncMock()
    db.fetch.return_value = [
        {"id": 30, "status": "progressing", "title": "e1", "project_id": 1},
        {"id": 31, "status": "qa", "title": "e2", "project_id": 1},
    ]
    db.fetchval.return_value = 99
    await close_open_epics(db, project_id=1)
    # record_event = fetchval INSERT INTO ticket_events. 각 에픽당 1회 = 2회.
    assert db.fetchval.await_count == 2
    for call in db.fetchval.await_args_list:
        # args: (query, ticket_id, kind, payload_json)
        assert call.args[1] in (30, 31)
        assert call.args[2] == "transition"
