# api/comments.py — 티켓 코멘트 GET/POST + agent-read 처리(D-DR6).
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.token import require_token
from app.comment.service import create_comment, list_comments, mark_read
from app.deps import get_db

router = APIRouter(prefix="/api/tickets", tags=["comments"], dependencies=[Depends(require_token)])


class CommentIn(BaseModel):
    author: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=4000)


@router.get("/{tid}/comments")
async def get_comments(tid: int, db=Depends(get_db)):
    return await list_comments(db, tid)


@router.post("/{tid}/comments", status_code=status.HTTP_201_CREATED)
async def post_comment(tid: int, body: CommentIn, db=Depends(get_db)):
    return await create_comment(db, ticket_id=tid, author=body.author, body=body.body)


@router.post("/{tid}/comments/{cid}/read")
async def read_comment(tid: int, cid: int, db=Depends(get_db)):
    ok = await mark_read(db, cid)
    if not ok:
        raise HTTPException(404, "comment not found or already read")
    return {"id": cid, "read": True}
