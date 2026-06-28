# tests/test_state.py — 상태기계 + 결과 스키마 검증(순수 단위).
from app.ticket.state import (
    ResultValidationError,
    can_reopen,
    can_transition,
    is_terminal,
    validate_agent_result,
)


def test_valid_transitions():
    assert can_transition("todo", "progressing")
    assert can_transition("progressing", "qa")
    assert can_transition("qa", "done")
    assert can_transition("qa", "progressing")


def test_all_states_freely_reachable():
    # workflow 제한 전면 해제 — 알려진 상태 간 모든 이동 허용.
    from app.ticket.state import STATES

    for frm in STATES:
        for to in STATES:
            assert can_transition(frm, to), f"{frm}->{to} should be allowed"


def test_unknown_states_rejected():
    assert not can_transition("nonsense", "todo")
    assert not can_transition("todo", "bogus")


def test_terminal_and_reopen():
    assert is_terminal("done")
    assert is_terminal("cancel")
    assert not is_terminal("progressing")
    assert can_reopen("done")
    assert can_reopen("cancel")
    assert not can_reopen("todo")


def test_validate_result_ok():
    p = validate_agent_result({"status": "succeeded", "summary": "did it"})
    assert p["status"] == "succeeded"
    p = validate_agent_result(
        {"status": "succeeded", "summary": "x", "gate": "pr_open", "diff_url": "http://u/1"}
    )
    assert p["gate"] == "pr_open"


def test_validate_result_malformed():
    cases = [
        {"status": "nope", "summary": "x"},          # bad status
        {"status": "succeeded"},                       # missing summary
        {"status": "succeeded", "summary": "  "},     # empty summary
        {"status": "succeeded", "summary": "x", "gate": "bogus"},  # bad gate
        {"status": "succeeded", "summary": "x", "events": "nope"},  # events not list
        "not-a-dict",
    ]
    for c in cases:
        try:
            validate_agent_result(c)
        except ResultValidationError:
            continue
        raise AssertionError(f"expected validation error for {c!r}")
