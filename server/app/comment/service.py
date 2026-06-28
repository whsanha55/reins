# comment/service.py — 티켓 코멘트(수동). agent-read ✓ 인디케이터(D-DR6).
from __future__ import annotations

from typing import TYPE_CHECKING

from app.ticket.service import record_event

if TYPE_CHECKING:
    from app.core.database import Database


async def list_comments(db: Database, ticket_id: int) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, ticket_id, author, body, created_at, read_at "
        "FROM ticket_comments WHERE ticket_id=$1 ORDER BY created_at ASC",
        ticket_id,
    )
    return [dict(r) for r in rows]


async def create_comment(
    db: Database, *, ticket_id: int, author: str, body: str
) -> dict:
    row = await db.fetchrow(
        "INSERT INTO ticket_comments (ticket_id, author, body) VALUES ($1, $2, $3) "
        "RETURNING *",
        ticket_id,
        author,
        body,
    )
    d = dict(row)
    await record_event(db, ticket_id, "comment", {"author": author, "body": body})
    return d


async def mark_read(db: Database, comment_id: int) -> bool:
    """에이전트 poll 시 코멘트 읽음 처리 → UI agent-read ✓ 인디케이터."""
    val = await db.fetchval(
        "UPDATE ticket_comments SET read_at=now() WHERE id=$1 AND read_at IS NULL RETURNING id",
        comment_id,
    )
    return val is not None
