# reins — 자율 칸반 커맨드센터

"지라 같은 칸반"이 아니라 **자율주행 프로젝트 매니저 + 인간 에스컬레이션 밸브**.
태스크 추적의 단일 진실 원천이자, 로컬 LLM 에이전트가 구현·PR까지 자율 주행하다가 정해진 게이트에서만 사람에게 결정을 묻는 시스템.

- **LLM은 100% 로컬**에서만 동작 — 서버는 LLM을 품지 않는다.
- 서버는 **상태·UI·알림**만 담당 (보안 모델의 근간).
- 알림은 Telegram(outbound-only), 결정은 웹 결정 큐에서 처리.

## 핵심 특징

- **프로젝트/티켓 보드** — `todo · progressing · qa · done · cancel`, 에픽(`parent_id` self-ref) 지원
- **결정 큐(Decision Queue)** — 에이전트가 4개 게이트에서 올리는 결정 요청을 한 곳에서
- **로컬 Claude Code 에이전트 연동** — 구현/PR은 자율, 결정만 사람
- **Telegram notify-only** — 결정핑 + 정보핑, 액션은 웹 큐로
- **에이전트 타임라인** — append-only 감사 로그(`ticket_events`)
- **heartbeat watchdog** — 정체(stalled) run 감지, 야간배치/아침 다이제스트
- **워크플로우/액션 엔진 추상화** — 향후 CI·스킬·배포 drop-in 확장 지점

## 아키텍처 한눈에

```
로컬 에이전트(Claude Code) ──API token──▶ reins 서버(FastAPI)
            │                                  │
            │ LLM/코드 실행은 로컬에서만         ├─ PostgreSQL (단일 진실 원천)
            ▼                                  ├─ 웹 UI (React)
         코드·PR 자율 생성                       └─ Telegram (outbound 알림 only)
```

> **서버에서 LLM 호출·코드 실행은 절대 금지.** 결정 큐·상태·알림만 서버 영역이다.

## 기술 스택

| 영역 | 기술 |
|------|------|
| **server** | Python 3.12 · FastAPI · asyncpg · APScheduler · PostgreSQL 16 |
| **ui** | React 18 · Vite · TypeScript · Tailwind CSS · TanStack Query |
| **인증** | API token (로컬/skills 원격). 비어있으면 로컬 개발은 인증 생략 |

## 저장소 구조

```
reins/
├── server/                 # FastAPI API + PostgreSQL
│   ├── app/
│   │   ├── main.py         # 앱 팩토리 · lifespan(db/dispatcher/watchdog)
│   │   ├── api/            # projects · tickets · comments · decisions · agent · ops
│   │   ├── agent/          # heartbeat watchdog
│   │   ├── auth/           # API token 인증
│   │   ├── core/           # notify(dispatcher/router) · database
│   │   ├── decision/  · ticket/  · comment/  · workflow/
│   │   └── config.py       # pydantic-settings
│   ├── tests/              # pytest (7종)
│   ├── migrate.py          # docs/schema.sql → DB 적용(멱등)
│   └── pyproject.toml
├── ui/                     # React/Vite/Tailwind
│   ├── src/
│   │   ├── App.tsx · router.ts · api.ts
│   │   └── components/      # Board · DecisionQueue · Sidebar · TicketDrawer · TicketForm
│   └── package.json
├── docs/
│   └── schema.sql          # 스키마 단일 진실 (DDL + 초기데이터)
├── TODOS.md                # v1 이후 / 지연 항목 (맥락 보존)
├── dev.sh                  # 로컬 dev 실행기 (backend:21001 + ui:21002)
└── README.md
```

## 시작하기

### 사전 요구

- Python 3.12+ ( [`uv`](https://docs.astral.sh/uv/) 권장 )
- Node.js 18+ (npm)
- PostgreSQL 16 (또는 docker-compose 사용)
- (선택) Telegram Bot Token — 알림 미사용 시 생략 가능

### 1) 저장소 클론

```bash
git clone <repo-url> reins && cd reins
```

### 로컬 dev 실행 — `dev.sh`

```bash
cp .env.example server/.env.local   # 값 채우기. config.py는 server/ 기준으로 .env.local/.env 로드
./local_run.sh
# backend → http://localhost:21001
# ui      → http://localhost:21002
# 로그     → .logs/{backend,frontend}.log
```

DB 마이그레이션은 별도 실행:

```bash
cd server && uv run python migrate.py
```

## 환경 변수

서버(`server/app/config.py`)가 읽는 값. `.env.local` > `.env` 순서로 로드.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `127.0.0.1` / `5432` / `reins` / `reins` / `changeme` | PostgreSQL 접속 정보 |
| `PORT` | `21001` | API 서버 포트 |
| `REINS_API_TOKEN` | _(빈)_ | API 인증 토큰. **비어있으면 인증 생략**(로컬 개발 편의) |
| `TELEGRAM_BOT_TOKEN` | _(빈)_ | 알림용 봇 토큰. 미설정 시 notify 스킵 |
| `TELEGRAM_CHAT_ID` | _(빈)_ | 발신 대상 chat_id (포럼 그룹) |
| `TELEGRAM_DEFAULT_CHAT_ID` | _(빈)_ | topic 자동생성 폭증 가드. 미설정 시 자동생성 없음 |
| `WATCHDOG_INTERVAL_SEC` | `300` | heartbeat 정체 감지 주기. `0` = off |
| `WATCHDOG_STALE_SEC` | `1800` | 30분 무업데이트 → stalled 판정 |
| `DIGEST_CRON_HOUR` | `8` | 아침 다이제스트 스케줄(KST). `0` = off |
| `CORS_ORIGINS` | `http://localhost:21002,http://localhost:3000` | CORS 허용 오리진(콤마 구분) |

## API 둘러보기

모든 라우트는 `REINS_API_TOKEN` 인증(토큰 비어있으면 생략). 공개 엔드포인트는 `/health`.

| Prefix | 영역 |
|--------|------|
| `GET /health` | 헬스 체크 (공개) |
| `/api/projects` | 프로젝트 |
| `/api/tickets` | 티켓 |
| `/api/tickets/{id}/...` | 티켓 코멘트 |
| `/api/decisions` | 결정 큐 |
| `/api/agent` | 에이전트(이벤트/heartbeat) |
| `/api/ops` | 운영(digest 등) |

## 핵심 원칙 (깨면 안 됨)

1. **서버에서 LLM/코드 실행 금지** — 보안 모델의 근간. LLM·코드 실행은 로컬 에이전트 영역.
2. **단일 진실 원천 = 자체 PostgreSQL** — GitHub 이슈 등 외부 이중화 없음.
3. **결정은 idempotent, 알림은 폴백 포함** — heartbeat watchdog(정체 run) · Telegram 폴백으로 크리티컬 갭(0) 유지.
4. **워크플로우/액션 엔진 위에 지을 것** — Phase2 재작성 방지.

## 로드맵

v1 이후·검토 항목은 [`TODOS.md`](TODOS.md)에서 관리(맥락 보존).

예정: CI 연동 · 스킬 흡수 · 토큰/비용 미터 · 프로젝트 간 우선순위 큐 · 프로젝트별 자율성 설정 · workflow-as-code UI · 보드에서 배포.

---

## 라이선스

본 프로젝트는 현재 별도의 공개 라이선스가 지정되지 않았습니다(All rights reserved).
