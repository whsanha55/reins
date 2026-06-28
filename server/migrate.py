# migrate.py — Python 마이그레이터. docs/schema.sql(단일진실)을 로컬 DB 에 적용.
# usage: uv run python migrate.py
# 종료 0 = 성공. CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS 로 멱등.
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg

from app.config import settings

# 기본: 레포 루트 docs/schema.sql. 컨테이너는 REINS_SCHEMA_PATH 로 덮어쓰기.
_DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "docs" / "schema.sql"
SCHEMA_PATH = Path(os.environ.get("REINS_SCHEMA_PATH") or _DEFAULT_SCHEMA)


def split_statements(sql: str) -> list[str]:
    """schema.sql 을 세미콜론 단위로 분할. 각 청크의 '--' 주석 라인은 제거 후 비어있으면 스킵."""
    out: list[str] = []
    for raw in sql.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            out.append(stmt)
    return out


async def main() -> int:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = split_statements(sql)
    conn = await asyncpg.connect(settings.database_url)
    applied = 0
    try:
        for stmt in statements:
            # 주석 라인 제거 후 로깅용 첫 토큰.
            clean = re.sub(r"--.*", "", stmt).strip()
            if not clean:
                continue
            await conn.execute(stmt)
            applied += 1
            head = clean.split()[0:4]
            print(f"  applied: {' '.join(head)} ...")
    finally:
        await conn.close()
    print(f"migration OK — {applied} statement(s) from {SCHEMA_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
