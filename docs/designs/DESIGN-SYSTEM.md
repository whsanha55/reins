# reins — Design System (v1, light)

> 출처: `ui-ux-pro-max` + `/plan-design-review` APP UI 규칙 보정 + 사용자 디자인 결정(라이트 테마·에픽 구분·티켓 코멘트).
> 톤: APP UI. 개인용 자율 칸반. 마케팅 배제, 밀도·속도 우선, 유틸리티 언어. 데스크탑 퍼스트.

## 테마 — 라이트

다크가 아닌 **화이트/슬레이트 라이트 톤**. 눈 편한 high-key. 데이터 밀집 도구에서 오히려 가독·대비 확보가 쉬움. CTA는 green-on-white 대비 부족 회피 → **slate-900 solid**, green은 상태/승인 인디케이터 전용.

## 타포그래피

| 역할 | 폰트 | 비고 |
|------|------|------|
| UI 본문/헤딩 | **IBM Plex Sans** | 개발 도구 미학, Inter/Roboto(기본 스택) 회피 |
| 코드·에이전트 로그·ID·메타 | **IBM Plex Mono** | 타임라인·이벤트·티켓 ID |
| 본문 크기 | 14px, 행간 1.55 | 본문 대비 4.5:1 유지 |
| 헤딩 | 16/20px, weight 600 | 섹션 = 역할 명시 |

금지: Inter, Roboto, Arial, system-ui, -apple-system, 필기체/장식체.

## 컬러 토큰

```css
--bg:         #F1F5F9;   /* slate-100, 앱 배경 */
--surface:    #FFFFFF;   /* 카드/패널 */
--surface-2:  #F8FAFC;   /* hover/활성 */
--border:     #E2E8F0;   /* slate-200 */
--border-2:   #CBD5E1;   /* slate-300, 입력/강조 */
--text:       #0F172A;   /* slate-900, 본문 (대비 ~17:1 on bg) */
--text-muted: #475569;   /* slate-600, 본문 보조 (4.5:1 통과) */
--text-dim:   #64748B;   /* slate-500, 메타 전용(비본문) */

--cta:        #0F172A;   /* primary 버튼 bg (slate-900), white 텍스트 */
--accent:     #16A34A;   /* green-600, 상태(success/승인) 전용 — 본문/CTA bg 아님 */
--decision:   #D97706;   /* amber-600, 결정필요 */
--decision-soft:#FEF3C7; /* amber-100, 결정 카드 bg */
--danger:     #DC2626;   /* red-600, 거부/failed */
--info:       #2563EB;   /* blue-600, 진행중 */
--epic:       #4F46E5;   /* indigo-600, 에픽 식별 전용 */
```

프로젝트 식별색(카드 좌측 점): emerald/sky/indigo/violet/amber/rose/cyan 순차 할당. 색+프로젝트명 텍스트 병기(a11y).

## 에픽 vs 태스크 (사용자 결정)

- **Epic** = 자식 티켓을 묶는 부모 티켓. 사이드바 "Epics" 섹션 + 보드 컬럼 최상단 배치.
- 에픽 카드: `border-2 indigo`, `EPIC` 배지, 제목, **진행도 바**(자식 done/total), 자식 수.
- 자식 태스크: 일반 카드 + 작은 에픽 색 점 + 에픽명 접두(또는 호버 툴팁). 에픽 클릭 → 자식 필터링 뷰.
- 생성 폼: type 라디오(Task/Epic), Epic 셀렉트(부모 지정).
- **스코프 파급**: tickets 테이블에 `parent_id`(self-ref, nullable) + 쿼리로 자식 집계. CEO-PLAN 스코프 확장(Design Review D2).

## 티켓 코멘트 (사용자 결정)

- 카드/드로어에 **Comments** 탭(Timeline과 분리). 리스트(작성자·시간·본문) + 하단 입력.
- timeline event = 자동(에이전트), comment = 수동(사용자). 에이전트가 다음 poll 시 코멘트를 맥락으로 읽음.
- 카드에는 코멘트 수 표시(`💬 N` → SVG 말풍선 아이콘으로 교체, 이모지 금지).
- **스코프 파급**: `ticket_comments`(id, ticket_id FK, author, body, created_at) + GET/POST API + T7 UI. CEO-PLAN 스코프 확장.

## 레이아웃

- 좌측 사이드바(Projects + Epics + 필터) + 메인 탭(Board·Decision Queue·New Ticket).
- 결정 큐 배지: nav 상시, 숫자 + amber 점. 최우선 위계.
- 카드 클릭 → 우측 드로어(Timeline/Comments 탭). 보드 유지.
- **보드 스코프(D-DR8)**: **단일 프로젝트**. 프로젝트 전환 = **사이드바**(헤더엔 현재 프로젝트 라벨만 표시). 한 칸반 = 한 프로젝트, 다중 에픽.
- **그룹 드롭다운(D-DR8)**: 없음(기본, flat 칸반) / 에픽별(**동일 칸반 디자인**, 에픽 헤더+진행도바로 섹션 분할, "에픽 없음" 섹션). segmented 아님 — 드롭다운.
- **정렬 드롭다운(D-DR8)**: 등록순(created, 기본) · 최근 변경순(updated) · 우선순위. 서버측 파라미터.
- **컬럼 헤더**: todo / **progressing** / qa / done / cancel — 풀 단어. 약어(`prog`) 금지.
- z-index: 10(base) · 20(sticky header) · 30(드로어) · 50(토스트).

## 상태 매핑

| 컴포넌트 | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---------|---------|-------|-------|---------|---------|
| Board | 컬럼 skeleton | "티켓 없음" + 새 티켓 버튼 | "로드 실패" + 재시도(`role=alert`) | 카드 렌더 | 일부 컬럼 |
| DecisionQueue | 카드 skeleton | "대기 결정 없음 ✓" | "로드 실패" + 재시도 | 승인 후 카드 fade-out(idempotent) | — |
| TicketForm | 제출 버튼 disabled | (폼) | 필드별 인라인 에러 + `aria-live` | 토스트 + 보드 반영 | — |
| Timeline | 로그 skeleton | "이벤트 없음" | "로드 실패" | 이벤트 스트림 | 더보기 커서 |
| Comments | 코멘트 skeleton | "첫 코멘트를 남겨주세요" | "로드 실패" | 새 코멘트 prepend | — |

## a11y / 반응형 / 금지 (AI slop)

- 본문 4.5:1, 포커스 링 가시(blue 2px), 키보드 탭 순서 = 시각 순서, `aria-live` 에러, 색 비의존(라벨 병기), `prefers-reduced-motion` 시 pulse/트랜지션 축소.
- 반응형: 1024+ 풀 레이아웃 · 768-1023 사이드바 축소+보드 가로스크롤 · <768 최소 보장(모바일은 텔레그램 주 표면).
- 금지: 보라/인디고 그라디언트 장식, 3-column feature grid, 색 원 안 아이콘, 중앙 정렬 남용, 풍선 radius, 장식 blob, 이모지 아이콘(→ Lucide SVG), "Welcome to" 카피. decorative shadows.
