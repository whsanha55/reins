# tests/test_topic_parser.py — topic 분류 + escape + 카드 render.
from app.core.notify.topic_parser import (
    GATES,
    classify,
    escape_html,
    render_card,
    render_release,
)


def test_classify_gate_is_decision():
    for g in GATES:
        assert classify(gate_type=g) == "decision"


def test_classify_event_kinds():
    assert classify(event_kind="stalled") == "stalled"
    assert classify(event_kind="digest") == "digest"
    assert classify(event_kind="created") == "info"
    assert classify() == "info"


def test_escape_html():
    assert escape_html("<b>x</b> & 'y'") == "&lt;b&gt;x&lt;/b&gt; &amp; 'y'"


def test_render_card_structure():
    html = render_card(title="티켓 #1", body="todo → progressing", category="info")
    assert html.startswith("<b>[정보]")
    assert "<pre>" in html
    assert "todo → progressing" in html  # escape 보존(한글/화살표 무결)


def test_render_card_escapes_html_injection():
    html = render_card(title="<i>x", body="<script>", category="decision")
    assert "<i>x" not in html
    assert "&lt;i&gt;x" in html
    assert "<script>" not in html


def test_render_release_lists_items_with_links():
    # #29: release 카드 = 헤더 + 항목별 #id 딥링크. title escape 보존.
    out = render_release(items=[
        {"id": 12, "title": "딥링크", "url": "https://h/project/1/t/12"},
        {"id": 13, "title": "<x>", "url": "https://h/project/1/t/13"},
    ])
    assert "2건 done" in out
    assert 'href="https://h/project/1/t/12"' in out
    assert ">#12<" in out
    assert "&lt;x&gt;" in out  # title escape
    assert "<x>" not in out
