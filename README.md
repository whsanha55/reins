# reins — 개인용 자율 칸반 커맨드센터

"지라 같은 칸반"이 아니라 **자율주행 프로젝트 매니저 + 인간 에스컬레이션 밸브**.
태스크 추적의 단일 진실 원천. LLM은 100% 로컬, 서버는 LLM 없이 상태·UI·알림만.

> 상세 설계·결정·구현태스크 → [`docs/CEO-PLAN.md`](docs/CEO-PLAN.md)

## 모노레포 구조
```
reins/
├── README.md
├── CLAUDE.md                    # 프로젝트 가이드 — 산출물 위치 규칙(외부 디렉토리 禁, docs/에)
├── TODOS.md                     # v1.1+/Phase2 지연 항목 (맥락 보존)
├── .gitignore
├── docs/
│   ├── CEO-PLAN.md              # 비전·스코프·아키텍처·결정 D1-D13·구현태스크 T0-T8
│   ├── tasks-ceo-review.jsonl   # /autoplan 집계용 태스크 (CEO)
│   ├── tasks-eng-review-*.jsonl # /autoplan 집계용 태스크 (Eng review, T0-T8)
│   └── *-eng-review-test-plan-*.md  # /qa 입력용 테스트 계획
├── server/                      # Go API + PostgreSQL (구현 예정)
└── ui/                          # React/Vite/Tailwind (구현 예정)
```
> 산출물 규칙: 모든 리뷰/설계/작업 산출물은 `docs/`에. 외부 디렉토리(`~/.gstack/`) 사용 금지. 상세는 [`CLAUDE.md`](CLAUDE.md).

## 핵심 결정 (D1-D6)
| # | 결정 |
|---|------|
| D1 | 진실 원천 = 자체 PostgreSQL (GitHub 이슈 폐기, 이중화 無) |
| D2 | 모드 = SCOPE EXPANSION |
| D3 | 자율성 = 게이트형, **배포=항상 허락** |
| D4 | v1 딜라이트 = 에이전트 타임라인 ✓ + 나이트배치/아침다이제스트 ✓ |
| D5 | 실행환경 = **서버 LLM 無, 로컬 100% LLM** (서버=상태/UI/알림 only) |
| D6 | 리포 = **모노레포** (server/ + ui/) |

## v1 스코프
- 보드(projects·tickets, todo/prog/qa/done/cancel) + 웹 UI + 결정 큐
- 로컬 Claude Code 에이전트: 구현/PR 자율, 4게이트에서 결정 요청
- Telegram notify-only (결정핑+정보핑), 액션은 웹 결정 큐
- 에이전트 타임라인(감사 로그) + 야간배치/아침다이제스트
- 워크플로우/액션 엔진 추상화 (Phase2: CI·스킬·배포 drop-in)

## 기술 스택
- **server**: Go (단일 바이너리) + PostgreSQL, docker
- **ui**: React + Vite + Tailwind, docker (nginx static)
- **infra**: docker-compose(postgres + api + ui + caddy/TLS) on con-jjong
- **auth**: API token (로컬/skills 원격) + Tailscale 권장(관리포트 격리)

## NOT in v1 (TODOS)
CI 연동 · 스킬 흡수(jissue/jpr/scoophub-ship) · 토큰/비용 미터 · 프로젝트 간 우선순위 큐 · 프로젝트별 자율성 설정 · workflow-as-code UI · 보드에서 배포

## 시작하기
1. `git init` (이 디렉토리에서)
2. **Eng Review 통과 ✓** (2026-06-28, [`docs/CEO-PLAN.md`](docs/CEO-PLAN.md) "Eng Review Decisions" D1-D13)
3. **Design Review 통과 ✓** (2026-06-28, [`docs/designs/`](docs/designs/) — DESIGN-SYSTEM.md + mockup, D-DR1..7)
4. **T0 spike 선행** — headless Claude Code로 1사이클(pull→코드생성→PR→결정요청) 증명 후, 결과 제약으로 T1부터 착수

## 핵심 원칙 (깨면 안 됨)
1. **서버에서 LLM/코드 실행 금지** — 보안 모델의 근간. D5.
2. **CRITICAL GAP 0 유지** — heartbeat watchdog(정체 run)·결정 idempotent·Telegram 폴백. [`docs/CEO-PLAN.md`](docs/CEO-PLAN.md) Section 2.
3. **워크플로우/액션 엔진 위에 지을 것** — Phase2 재작성 방지. D6/T8.
