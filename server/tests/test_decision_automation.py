# tests/test_decision_automation.py — resolve(approved) 자동 머지/배포/done 자동화.
# AsyncMock db + service 수준 monkeypatch (merge_pr_github/create_job/transition/record_event).
from unittest.mock import AsyncMock

import pytest

import app.decision.github_merge as gm
import app.decision.service as svc
from app.decision.github_merge import MergeError, extract_pr_number, merge_pr_github
from app.decision.service import resolve


def _decision(did: int = 6, gate: str = "merge", status: str = "pending") -> dict:
    return {
        "id": did,
        "ticket_id": 36,
        "gate": gate,
        "summary": "머지 결정",
        "status": status,
        "resolution_note": None,
    }


# ── 1. PR 번호 추출 ───────────────────────────────────────────────
def test_extract_pr_number():
    assert extract_pr_number("https://github.com/whsanha55/reins/pull/17") == 17
    assert extract_pr_number("https://github.com/whsanha55/reins/pull/17/files") == 17
    assert extract_pr_number("https://github.com/whsanha55/reins/pull/42/") == 42
    assert extract_pr_number("not a url") is None
    assert extract_pr_number(None) is None


# ── 1b. _latest_diff_url — asyncpg JSONB str 처리 ─────────────────
async def test_latest_diff_url_handles_jsonb_str():
    from app.decision.service import _latest_diff_url

    db = AsyncMock()
    db.fetchrow.return_value = {"payload": '{"url": "https://github.com/whsanha55/reins/pull/17"}'}
    url = await _latest_diff_url(db, 36)
    assert url == "https://github.com/whsanha55/reins/pull/17"


# ── 2. merge gate 승인 → 머지 + deploy job + done ─────────────────
async def test_resolve_approved_merge_triggers_merge_deploy_done(monkeypatch):
    db = AsyncMock()
    db.fetchrow.side_effect = [
        _decision(gate="merge"),  # resolve SELECT decision
        {"payload": {"url": "https://github.com/whsanha55/reins/pull/17"}},  # _latest_diff_url
    ]
    db.fetchval.side_effect = [6, 1]  # applied_id, project_id
    merged = AsyncMock(return_value={"merged": True, "sha": "abc"})
    monkeypatch.setattr(svc, "merge_pr_github", merged)
    create_job = AsyncMock(return_value={"id": 99})
    monkeypatch.setattr(svc, "create_job", create_job)
    transition = AsyncMock()
    monkeypatch.setattr(svc, "transition_ticket", transition)
    monkeypatch.setattr(svc, "record_event", AsyncMock(return_value=1))

    out = await resolve(db, AsyncMock(), decision_id=6, resolution="approved")

    assert out["applied"] is True
    merged.assert_awaited_once()
    assert merged.call_args.kwargs["pr_number"] == 17
    create_job.assert_awaited_once()
    assert create_job.call_args.kwargs["triggered_by"] == "merge-auto"
    transition.assert_awaited_once()
    assert transition.call_args.kwargs["to"] == "done"


# ── 3. 머지 실패 → progressing 유지 + automation_failed ───────────
async def test_resolve_approved_merge_failure_keeps_progressing(monkeypatch):
    db = AsyncMock()
    db.fetchrow.side_effect = [_decision(gate="merge"), {"payload": {"url": ".../pull/17"}}]
    db.fetchval.side_effect = [6, 1]
    monkeypatch.setattr(svc, "merge_pr_github", AsyncMock(side_effect=MergeError("boom")))
    create_job = AsyncMock()
    monkeypatch.setattr(svc, "create_job", create_job)
    transition = AsyncMock()
    monkeypatch.setattr(svc, "transition_ticket", transition)
    record_ev = AsyncMock(return_value=1)
    monkeypatch.setattr(svc, "record_event", record_ev)

    await resolve(db, AsyncMock(), decision_id=6, resolution="approved")

    create_job.assert_not_awaited()
    transition.assert_not_awaited()
    kinds = [c.args[2] for c in record_ev.call_args_list]
    assert "automation_failed" in kinds


# ── 4. deploy gate → 머지 생략, deploy job + done ─────────────────
async def test_resolve_approved_deploy_only_creates_job(monkeypatch):
    db = AsyncMock()
    db.fetchrow.return_value = _decision(gate="deploy")
    db.fetchval.side_effect = [6, 1]
    merged = AsyncMock()
    monkeypatch.setattr(svc, "merge_pr_github", merged)
    create_job = AsyncMock(return_value={"id": 99})
    monkeypatch.setattr(svc, "create_job", create_job)
    transition = AsyncMock()
    monkeypatch.setattr(svc, "transition_ticket", transition)
    monkeypatch.setattr(svc, "record_event", AsyncMock())

    await resolve(db, AsyncMock(), decision_id=6, resolution="approved")

    merged.assert_not_awaited()
    create_job.assert_awaited_once()
    transition.assert_awaited_once()
    assert transition.call_args.kwargs["to"] == "done"


# ── 5. diff_url 없음 → automation_failed, 머지 X ──────────────────
async def test_resolve_approved_no_diff_url_fails_gracefully(monkeypatch):
    db = AsyncMock()
    db.fetchrow.side_effect = [_decision(gate="merge"), None]  # diff 행 없음
    db.fetchval.side_effect = [6, 1]
    merged = AsyncMock()
    monkeypatch.setattr(svc, "merge_pr_github", merged)
    create_job = AsyncMock()
    monkeypatch.setattr(svc, "create_job", create_job)
    transition = AsyncMock()
    monkeypatch.setattr(svc, "transition_ticket", transition)
    record_ev = AsyncMock(return_value=1)
    monkeypatch.setattr(svc, "record_event", record_ev)

    await resolve(db, AsyncMock(), decision_id=6, resolution="approved")

    merged.assert_not_awaited()
    create_job.assert_not_awaited()
    transition.assert_not_awaited()
    kinds = [c.args[2] for c in record_ev.call_args_list]
    assert "automation_failed" in kinds


# ── 6. idempotent — 재클릭(applied=False) → 자동화 미진입 ──────────
async def test_resolve_idempotent_skips_automation(monkeypatch):
    db = AsyncMock()
    db.fetchrow.return_value = _decision(status="approved")  # 이미 resolved
    db.fetchval.return_value = None  # UPDATE WHERE pending → None
    merged = AsyncMock()
    monkeypatch.setattr(svc, "merge_pr_github", merged)

    out = await resolve(db, AsyncMock(), decision_id=6, resolution="approved")

    assert out["applied"] is False
    merged.assert_not_awaited()


# ── 7. merge_pr_github — squash PUT 요청 + 409 → MergeError ────────
class _FakeResp:
    def __init__(self, status_code: int, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp
        self.captured = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def put(self, url, headers=None, json=None):
        self.captured = {"url": url, "headers": headers, "json": json}
        return self._resp


async def test_merge_pr_github_puts_squash(monkeypatch):
    client = _FakeClient(_FakeResp(200, {"merged": True, "sha": "abc"}))
    monkeypatch.setattr(gm.httpx, "AsyncClient", lambda *a, **kw: client)
    monkeypatch.setattr(gm.settings, "GITHUB_TOKEN", "tok123")

    res = await merge_pr_github(pr_number=17, commit_title="#36 auto-merge")

    assert res == {"merged": True, "sha": "abc"}
    assert "pulls/17/merge" in client.captured["url"]
    assert client.captured["json"]["merge_method"] == "squash"
    assert client.captured["json"]["commit_title"] == "#36 auto-merge"
    assert client.captured["headers"]["Authorization"] == "token tok123"


async def test_merge_pr_github_409_raises(monkeypatch):
    client = _FakeClient(_FakeResp(409, text="{}"))
    monkeypatch.setattr(gm.httpx, "AsyncClient", lambda *a, **kw: client)
    monkeypatch.setattr(gm.settings, "GITHUB_TOKEN", "tok123")

    with pytest.raises(MergeError):
        await merge_pr_github(pr_number=17)


async def test_merge_pr_github_no_token_raises(monkeypatch):
    # settings.GITHUB_TOKEN 비어있음 → MergeError (로컬 no-op 유도).
    monkeypatch.setattr(gm.settings, "GITHUB_TOKEN", "")
    with pytest.raises(MergeError):
        await merge_pr_github(pr_number=17)
