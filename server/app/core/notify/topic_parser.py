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


def render_card(
    *, title: str, body: str, category: str, label: str | None = None, url: str | None = None
) -> str:
    """HTML 카드. 동적값은 전부 escape. Telegram parse_mode=HTML. url 지정 시 링크 줄 추가(#27)."""
    cat = CATEGORY_LABEL.get(category, category)
    head = escape_html(label) if label else cat
    card = (
        f"<b>[{head}] {escape_html(title)}</b>\n"
        f"<pre>{escape_html(body)}</pre>"
    )
    if url:
        card += f'\n<a href="{escape_html(url)}">{escape_html(url)}</a>'
    return card


def render_release(*, items: list[dict]) -> str:
    """묶음 done 1개 release 카드. items=[{id,title,url}]. #29: 배포 시 우루루 알림 → 1개.
    각 줄 #id 가 딥링크. <pre> 미사용(앵커 클릭 가능)."""
    head = f"<b>[release] {len(items)}건 done</b>"
    lines = "\n".join(
        f'• <a href="{escape_html(it["url"])}">#{it["id"]}</a> {escape_html(it["title"])}'
        for it in items
    )
    return f"{head}\n{lines}"


# 결정 카드 인라인 키보드 콜백 접두어. api/telegram.py webhook 과 쌍.
RESOLVE_CB_PREFIX = "resolve:"


def resolve_keyboard(decision_id: int) -> dict:
    """decision 카드 인라인 키보드. callback_data=resolve:{id}:{resolution}.
    사람이 버튼 → Telegram webhook → resolve 자동(approved/rejected/changes)."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ 승인", "callback_data": f"resolve:{decision_id}:approved"},
                {"text": "❌ 거절", "callback_data": f"resolve:{decision_id}:rejected"},
                {"text": "🔧 수정", "callback_data": f"resolve:{decision_id}:changes"},
            ]
        ]
    }
