# ticket/state.py — 상태기계 + 결과 스키마 검증(순수 로직, DB 무관).
# D6: 결과 스키마 = 서버 canonical. malformed → 카드 정지(조용히 옮기지 않음).
from __future__ import annotations

from typing import Any

# tickets.status — 풀 단어(약어 금지, D-DR8).
STATES = ("todo", "progressing", "qa", "done", "cancel")
TERMINAL = frozenset({"done", "cancel"})

# ponytail: workflow 제한 전면 해제 — 어떤 상태든 어디든 자유 이동(사용자 요청).
# _TRANSITIONS 화이트리스트 폐기. can_transition 은 알려진 상태 간 이동만 허용(나머지 자유).
_TRANSITIONS = frozenset()  # 사용 안 함(히스토리 보존)

# 에이전트 결과 status(서버 canonical 스키마).
RESULT_STATUS = frozenset({"succeeded", "failed"})


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def can_transition(frm: str, to: str) -> bool:
    """제한 없음 — frm/to 가 알려진 상태면 모든 이동 허용."""
    return frm in STATES and to in STATES


def can_reopen(status: str) -> bool:
    """reopen = done|cancel → todo (명시적 엔드포인트만)."""
    return status in TERMINAL


class ResultValidationError(ValueError):
    """에이전트 결과 스키마 위반. malformed → agent_run failed, 카드 정지."""


def validate_agent_result(payload: Any) -> dict:
    """D6 서버 canonical 스키마 검증. 위반 시 ResultValidationError.

    필수: status(in succeeded|failed), summary(비빈 str).
    선택: gate(GATES 중 하나), gate_summary(str), diff_url(str), events(list).
    """
    if not isinstance(payload, dict):
        raise ResultValidationError("result must be a JSON object")
    status = payload.get("status")
    if status not in RESULT_STATUS:
        raise ResultValidationError(f"status must be one of {sorted(RESULT_STATUS)}")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ResultValidationError("summary must be a non-empty string")

    gate = payload.get("gate")
    if gate is not None:
        # GATES defined in topic_parser (4게이트). 지연 import 순환 회피.
        from app.core.notify.topic_parser import GATES

        if gate not in GATES:
            raise ResultValidationError(f"gate must be one of {list(GATES)} or null")

    for key in ("gate_summary", "diff_url"):
        val = payload.get(key)
        if val is not None and not isinstance(val, str):
            raise ResultValidationError(f"{key} must be a string or null")

    events = payload.get("events")
    if events is not None:
        if not isinstance(events, list):
            raise ResultValidationError("events must be a list")
        for ev in events:
            if not isinstance(ev, dict) or not isinstance(ev.get("kind"), str):
                raise ResultValidationError("each event must be an object with string kind")

    return payload
