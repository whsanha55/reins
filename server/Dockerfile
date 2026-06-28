# reins API — Python(FastAPI)/uvicorn. 서버 LLM/코드실행 禁(D5).
# build context = 레포 루트(compose 지정). server/ + docs/ 모두 접근.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY server/pyproject.toml ./
RUN uv sync --no-dev

COPY server/app ./app
COPY server/migrate.py ./
# 스키마 단일진실을 이미지에 포함(마이그레이션용).
COPY docs/schema.sql /app/schema.sql
ENV REINS_SCHEMA_PATH=/app/schema.sql

EXPOSE 21001
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "21001"]
