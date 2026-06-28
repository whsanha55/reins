# core/notify/topic_parser.py — ★ 전용 topic 파서.
# 역할 1: 이벤트 소스(gate_type/event_kind) → topic 분류(decision/stalled/digest/info).
# 역할 2: escape_html + HTML 카드 render (Telegram parse_mode=HTML).
from __future__ import annotations

from html import escape

# 4게이트 (D3 게이트형 자율성). 결정 큐 카드의 gate 구분.
GATES = ("pr_open", "merge", "deploy", "spec_ambiguous")

GATE_LABEL = {
    "pr_open": "PR 오픈",
    "merge": "머지",
    "deploy": "배포",
    "spec_ambiguous": "스펙 애매",
}

# 분류 단위 = 이벤트 topic. router 가 topic_id 해석(부재 시 provisioner 자동생성).
CATEGORIES = ("decision", "stalled", "digest", "info")

CATEGORY_LABEL = {
    "decision": "결정필요",
    "stalled": "정체",
    "digest": "아침다이제스트",
    "info": "정보",
}


def classify(*, gate_type: str | None = None, event_kind: str | None = None) -> str:
    """이벤트 소스 → category. gate_type 우선(4게이트=결정)."""
    if gate_type in GATES:
        return "decision"
    if event_kind == "stalled":
        return "stalled"
    if event_kind == "digest":
        return "digest"
    return "info"


def escape_html(s: str) -> str:
    return escape(s, quote=False)


def render_card(*, title: str, body: str, category: str, label: str | None = None) -> str:
    """HTML 카드. 동적값은 전부 escape. Telegram parse_mode=HTML."""
    cat = CATEGORY_LABEL.get(category, category)
    head = escape_html(label) if label else cat
    return (
        f"<b>[{head}] {escape_html(title)}</b>\n"
        f"<pre>{escape_html(body)}</pre>"
    )
