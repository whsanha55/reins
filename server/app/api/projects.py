# api/projects.py — 프로젝트 CRUD.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.token import require_token
from app.deps import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_token)])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str | None = None
    description: str | None = None
    host_path: str | None = None              # deploy-as-code: agent 실행 호스트 경로. null=deploy 불가


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = None
    description: str | None = None
    host_path: str | None = None


class SprintIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.get("")
async def list_projects(db=Depends(get_db)):
    rows = await db.fetch("SELECT * FROM projects ORDER BY created_at ASC")
    return [dict(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectIn, db=Depends(get_db)):
    row = await db.fetchrow(
        "INSERT INTO projects (name, color, description, host_path) VALUES ($1, $2, $3, $4) RETURNING *",
        body.name,
        body.color,
        body.description,
        body.host_path,
    )
    return dict(row)


@router.get("/{pid}")
async def get_project(pid: int, db=Depends(get_db)):
    row = await db.fetchrow("SELECT * FROM projects WHERE id=$1", pid)
    if not row:
        raise HTTPException(404, "project not found")
    return dict(row)


@router.patch("/{pid}")
async def update_project(pid: int, body: ProjectPatch, db=Depends(get_db)):
    sets, args = [], []
    if body.name is not None:
        args.append(body.name)
        sets.append(f"name=${len(args)}")
    if body.color is not None:
        args.append(body.color)
        sets.append(f"color=${len(args)}")
    if body.description is not None:
        args.append(body.description)
        sets.append(f"description=${len(args)}")
    if body.host_path is not None:
        args.append(body.host_path or None)         # 빈 문자열 → null 정규화(초기화 지원)
        sets.append(f"host_path=${len(args)}")
    if not sets:
        return await get_project(pid, db)
    args.append(pid)
    row = await db.fetchrow(
        f"UPDATE projects SET {', '.join(sets)} WHERE id=${len(args)} RETURNING *", *args
    )
    if not row:
        raise HTTPException(404, "project not found")
    return dict(row)


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(pid: int, db=Depends(get_db)):
    await db.execute("DELETE FROM projects WHERE id=$1", pid)
    return None


# ── sprints (#14): 프로젝트별 스프린트. 최신 started_at = 활성. 보드가 done/cancel 노출 필터에 사용.
@router.get("/{pid}/sprints")
async def list_sprints(pid: int, db=Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM sprints WHERE project_id=$1 ORDER BY started_at DESC, id DESC", pid
    )
    return [dict(r) for r in rows]


@router.post("/{pid}/sprints", status_code=status.HTTP_201_CREATED)
async def create_sprint(pid: int, body: SprintIn, db=Depends(get_db)):
    if not await db.fetchrow("SELECT id FROM projects WHERE id=$1", pid):
        raise HTTPException(404, "project not found")
    row = await db.fetchrow(
        "INSERT INTO sprints (project_id, name) VALUES ($1, $2) RETURNING *", pid, body.name
    )
    return dict(row)
