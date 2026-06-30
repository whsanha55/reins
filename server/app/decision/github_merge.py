# decision/github_merge.py — resolve(approved, gate=merge) 자동 머지.
# GitHub REST API PUT /repos/{owner}/{repo}/pulls/{n}/merge (squash).
# 순수 함수 — 호출자(decision/service.resolve)가 상태 복구/notify 담당.
from __future__ import annotations

import logging
import re

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_PR_RE = re.compile(r"/pull/(\d+)(?:/|$)")


class MergeError(RuntimeError):
    """머지 실패 — 토큰 미설정/404/405/409(이미 머지됨)/네트워크. 호출자가 automation_failed 처리."""


def extract_pr_number(diff_url: str | None) -> int | None:
    """PR URL → 번호. https://github.com/{owner}/{repo}/pull/{n}[/files]. 없으면 None."""
    if not diff_url:
        return None
    m = _PR_RE.search(diff_url)
    return int(m.group(1)) if m else None


async def merge_pr_github(*, pr_number: int, commit_title: str | None = None) -> dict:
    """squash 머지. 성공 → {"merged": True, "sha": ...}. 실패 → MergeError."""
    if not settings.GITHUB_TOKEN:
        raise MergeError("GITHUB_TOKEN not configured")
    url = (
        f"https://api.github.com/repos/{settings.GITHUB_REPO_OWNER}"
        f"/{settings.GITHUB_REPO_NAME}/pulls/{pr_number}/merge"
    )
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    body: dict = {"merge_method": "squash"}
    if commit_title:
        body["commit_title"] = commit_title
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise MergeError(f"네트워크 오류: {e}") from e
    if resp.status_code == 405:
        raise MergeError("머지 불가(405) — 충돌 또는 PR 상태")
    if resp.status_code == 409:
        raise MergeError("이미 머지됨(409)")
    if resp.status_code >= 400:
        raise MergeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return {"merged": bool(data.get("merged", True)), "sha": data.get("sha")}
