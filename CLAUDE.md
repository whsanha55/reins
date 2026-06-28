# reins — 프로젝트 가이드

> 전역 지침(`~/.claude/CLAUDE.md`) + 이 파일이 우선. gstack 스킬 동작이 아래 규칙과 충돌하면 **이 규칙이 이긴다.**

## 산출물 위치 규칙 (하드 룰)

**모든 리뷰/설계/작업 산출물은 프로젝트 내부에 둔다. 외부 디렉토리 사용 금지.**

- ✅ 산출물 = `docs/` 아래:
  - `CEO-PLAN.md` (CEO 리뷰)
  - `tasks-*-review.jsonl` (/autoplan 집계용 태스크)
  - `*-test-plan-*.md` (/qa 입력용 테스트 계획)
  - 리뷰 보고서, 설계 문서, spike 노트 등
- ❌ **금지**: `~/.gstack/projects/<slug>/` 등 외부 경로에 산출물 작성. gstack 스킬이 기본적으로 `~/.gstack/`에 쓰더라도, **이 프로젝트에선 `docs/`로 리디렉션**할 것.
- ⚠️ 예외 (옮기지 말 것): `~/.gstack/projects/<slug>/timeline.jsonl`, `*-reviews.jsonl` — gstack 내부 상태/인덱스. 옮기면 review dashboard·readiness 검사가 깨짐. 산출물이 아니라 인프라 상태 파일.

## 이유

- 이식성·추적: 산출물이 프로젝트와 함께 git에 들어가야 다른 기기/세션에서 보존됨.
- 외부(`~/.gstack/`)는 기기 로컬 상태라, repo만 옮기면 산출물이 유실됨.

## 적용

gstack 스킬(`/plan-*-review`, `/spec`, `/autoplan` 등) 실행 시:
- 산출물 경로를 스킬 기본값(`~/.gstack/projects/<slug>/...`) 대신 `docs/...`로 쓸 것.
- 이미 외부에 쓰여 있으면 즉시 `docs/`로 옮길 것.
