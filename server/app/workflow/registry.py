# workflow/registry.py — 액션 엔진 추상화(T8). switch 하드코딩, 인터페이스/팩토리 禁(ponytail).
# v1: 전이 → 기본 액션 매핑(하드코딩). Phase2 drop-in: workflow_actions 테이블 + ci/deploy.
# 신규 액션 타입 = 이 매핑/테이블에 한 줄 추가. 유지(D11-A, README 원칙3).
from __future__ import annotations

# 전이 → 발생 액션. agent_run=클레임, decision=결정큐, telegram=정보성 notify,
# ci/deploy=Phase2 placeholder(현재 미발생).
DEFAULT_ACTIONS: dict[tuple[str, str], list[str]] = {
    ("todo", "progressing"): ["agent_run"],
    ("progressing", "qa"): ["telegram"],       # Phase2: + "ci"
    ("qa", "done"): ["telegram"],              # Phase2: + "deploy"(gate)
    ("qa", "progressing"): ["telegram"],
}

# 4게이트(결정 요청). 에이전트가 결과 push 시 gate 필드로 요청 → decision 액션.
GATES = ("pr_open", "merge", "deploy", "spec_ambiguous")


def actions_for(frm: str, to: str) -> list[str]:
    """전이에 해당하는 액션 목록. 미정의 전이는 telegram(정보성) 기본."""
    return DEFAULT_ACTIONS.get((frm, to), ["telegram"])
