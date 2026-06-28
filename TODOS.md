# TODOS — reins

v1 이후 / 구현 중 검토 항목. 3개월 뒤에도 "왜 미뤘는지"가 남도록 맥락 보존.

> 출처 표시: `[CEO]` = CEO-PLAN에서 이관, `[ENG]` = /plan-eng-review에서 신규.

---

## Phase2 — CEO-PLAN에서 이관

### [CEO] CI 연동
- **What**: `progressing→qa` 시 CI 트리거, 결과를 카드 배지로 표시.
- **Why**: 품질 게이트 자동화. 현재는 에이전트 수동 판단.
- **Context**: workflow_actions의 `ci` 액션으로 drop-in. T8 엔진 확장점 위에 구현.
- **Depends on**: T8 엔진 안정, v1 운영.

### [CEO] 스킬 흡수 (jissue/jpr/scoophub-ship)
- **What**: 기존 스킬의 코드전달/PR 로직을 시스템 액션으로 흡수.
- **Why**: 에이전트가 스킬을 외부 호출하지 않고 시스템 내장 액션으로 통합.
- **Context**: v1은 에이전트가 스킬을 로컬에서 호출. Phase2에 액션으로 내재화.
- **Depends on**: T8 엔진, jissue/jpr/scoophub-ship 안정.

### [CEO] 토큰/비용 미터 + 예산 가드레일
- **What**: 에이전트 LLM 토큰/비용 추적 + 예산 초과 시 정지.
- **Why**: 로컬 LLM 100%라도 비용 가시성·가드레일 필요.
- **Context**: CEO-PLAN D4c DEFERRED. agent_run에 비용 필드 추가.
- **Depends on**: T6 에이전트.

### [CEO] 프로젝트 간 우선순위 큐
- **What**: "에이전트가 다음에 뭘 할까" 단일 뷰(다중 프로젝트).
- **Why**: 다중 프로젝트 차별화. 현재는 프로젝트 내 큐만.
- **Context**: CEO-PLAN D4d DEFERRED.
- **Depends on**: v1 다중 프로젝트 운영.

### [CEO] 프로젝트별 자율성 설정
- **What**: 프로젝트 단위 자율성(scoophub=고자율, gonamu=보조).
- **Why**: 프로젝트 성격에 따라 게이트 수 조절.
- **Context**: 현재는 단일 자율성 정책(D3 게이트형).
- **Depends on**: v1 게이트 엔진.

### [CEO] workflow-as-code YAML/UI
- **What**: 전이 규칙을 코드(YAML) 또는 UI로 편집.
- **Why**: v1은 하드코딩 기본 전이. 사용자 정의 워크플로.
- **Context**: T8 switch에서 시작, 점진적 외부화.
- **Depends on**: T8 엔진.

### [CEO] 보드에서 배포 (deploy 액션)
- **What**: 보드/결정 큐에서 직접 배포 트리거.
- **Why**: 배포 자동화. 현재는 수동(con-jjong).
- **Context**: 배포는 항상 게이트(D3). deploy 액션 Phase2.
- **Depends on**: con-jjong 배포 자동화, T8 엔진.

---

## v1.1 — /plan-eng-review 신규

### [ENG] heartbeat event log 보존/아카이빙 정책
- **What**: `ticket_events`(append-only) 보존 기한 또는 아카이빙 메커니즘.
- **Why**: 무한 증가 시 타임라인/보드 쿼리 지연.
- **Context**: D8 결정 — v1은 무한 + 커서 페이지네이션. 데이터 충분히 쌓인 뒤 보존 기한(예: 180일) 또는 cold archive 설계. 감사 보존(D4a) vs 쿼리 성능 트레이드오프.
- **Depends on**: v1 운영 데이터 축적(수개월).

### [ENG] 실제 Claude Code 출력 eval 스위트
- **What**: mock 외 실제 Claude Code 헤드리스 출력으로 결과 스키마 준수·4게이트 판단 품질 eval.
- **Why**: D7 — mock만으로는 유일한 비결정 컴포넌트(LLM 출력) 검증 안 됨. D6 스키마 검증의 실제 신뢰 확보.
- **Context**: 최소 1회 실제 검증은 v1(D12-A). 지속 eval 스위트는 별도 — 결과 스키마 준수율, 게이트 판단 정확도, malformed 발생률 추적.
- **Depends on**: T0 spike, T6 에이전트.

---

## v1.1+ — /plan-design-review 신규

### [DESIGN] 다크모드/테마 토글
- **What**: 라이트 단일 → 다크/라이트 토글 + 시스템 설정 추종.
- **Why**: D-DR7 — v1은 라이트 전용 속도 우선. 야간 사용·선호 대응.
- **Context**: DESIGN-SYSTEM.md 토큰 변수화되어 추가 용이. Tailwind `dark:` 변형 전면 적용 비용.
- **Depends on**: T7 완료, 사용자 요청.

### [DESIGN] 에픽 진행도 집계 — 실시간 vs 캐시
- **What**: 에픽 진행도바(done/total) 연산 방식 결정.
- **Why**: 자식 티켓 많아지면 보드 로딩 시 집계 비용.
- **Context**: v1은 카드 수 적어 즉시 집계 무방. 데이터 축적 후 materialized view/캐시 검토.
- **Depends on**: v1 운영 데이터.

### [DESIGN] 모바일 웹 접근 최소 보장 강화
- **What**: <768px 보드/결정큐 응급 접근 UX 개선.
- **Why**: 모바일은 텔레그램 주표면이나, 외출 중 웹 긴급 승인 시 최소 보장 필요.
- **Context**: v1 데스크탑 퍼스트. 모바일 결정큐 단일 컬럼 리스트 + 44px 터치타겟.
- **Depends on**: 사용자 사용 패턴 확인.

---

## 검토 보류 (사용자 제외)
- **Tailscale 관리포트 하드 요구사항 검토** — outside voice가 MED로 짚은 보안 항목. D13에서 TODO 제외됨. v1은 "권장" 유지 but 공용 노출 엔드포인트(읽기전용 보드) 명시적 분리는 구현 시 권장(D12 다이어그램 정리에 일부 반영).
