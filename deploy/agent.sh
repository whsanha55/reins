#!/usr/bin/env bash
# deploy/agent.sh — reins 보드 배포 host agent. jjong 호스트에서 systemd 로 구동.
#
# 루프: POST /deploy/reclaim-stale(기동 1회) → POST /deploy/claim(폴링)
#       → git 동기화(fetch/reset) + bash deploy.sh → POST /deploy/{id}/result.
# 책임 분리(model 2 deploy-as-code): 본 agent=공통 git 동기화. 각 repo deploy.sh=빌드(docker compose up 등).
# 자기 배포(reins→reins) 안전: 본 프로세스는 호스트. api 컨테이너 재기동 중에도 계속 실행,
#   result POST 는 성공할 때까지 재시도 루프.
#
# 주의 — repo 밖 안정 경로에서 실행할 것: 본 스크립트가 배포 대상 repo(~/reins) 안에 있으면,
#   git reset --hard 가 같은 inode 를 truncate+재기록해서 실행 중인 루프를 오염시킨다.
#   따라서 systemd ExecStart=/etc/reins/agent.sh (복사본) 로 구동. agent.sh 갱신 시 재복사+재시작.
#
# 설정(env 또는 EnvironmentFile):
#   REINS_API_URL   필수 — reins api 베이스(예: http://127.0.0.1:21001)
#   REINS_TOKEN     필수 — reins API 토큰(REINS_API_TOKEN 과 동일)
#   POLL_INTERVAL   옵션 — 폴링 주기 초(기본 5)
#   LOG_TAIL_LINES  옵션 — job 에 저장할 로그 마지막 N줄(기본 200)
# 의존: curl jq git bash. 모두 시스템 패키지.
set -uo pipefail

: "${REINS_API_URL:?REINS_API_URL required (e.g. http://127.0.0.1:21001)}"
: "${REINS_TOKEN:?REINS_TOKEN required (reins API token)}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-200}"
AUTH=(-H "Authorization: Bearer $REINS_TOKEN")

echo "[agent] start — poll $REINS_API_URL every ${POLL_INTERVAL}s, tail=${LOG_TAIL_LINES}"

# 기동 1회: 직전 실행 크래시로 남은 stuck running job → failed 정리.
curl -sf -X POST "$REINS_API_URL/api/deploy/reclaim-stale" "${AUTH[@]}" >/dev/null 2>&1 || true

while true; do
  # 1) 클레임. 204(대기 없음)/빈 본문 → 대기.
  resp=$(curl -sf -X POST "$REINS_API_URL/api/deploy/claim" "${AUTH[@]}" 2>/dev/null) || resp=""
  id=$(printf '%s' "$resp" | jq -r '.id // empty' 2>/dev/null)
  if [[ -z "$id" ]]; then
    sleep "$POLL_INTERVAL"
    continue
  fi

  host_path=$(printf '%s' "$resp" | jq -r '.host_path // empty')
  ref=$(printf '%s' "$resp" | jq -r '.ref // "main"')
  echo "[agent] claimed job #${id} — ${host_path:-<no host_path>} @ ${ref}"

  # 2) git 동기화 + deploy.sh. 실패해도 종료 X(결과를 job 에 기록).
  if [[ -z "$host_path" ]] || [[ ! -d "$host_path/.git" ]]; then
    log="[agent] host_path 가 비었거나 git 저장소 아님: '$host_path'"
    code=1
  else
    log=$(cd "$host_path" 2>&1 && git fetch --prune origin 2>&1 \
          && git reset --hard "origin/${ref}" 2>&1 && bash deploy.sh 2>&1)
    code=$?
  fi
  tail_log=$(printf '%s' "$log" | tail -n "$LOG_TAIL_LINES")
  [[ $code -eq 0 ]] && status=success || status=failed
  echo "[agent] job #${id} → ${status} (exit ${code})"

  # 3) 결과 회신. api 재기동 중일 수 있음(자기 배포 실패 등) → 성공까지 재시도.
  #    job 은 반드시 결과를 받아야 함(미회신 시 영구 running → reclaim-stale 10분 대기).
  payload=$(jq -nc --arg s "$status" --argjson c "$code" --arg l "$tail_log" \
    '{status:$s, exit_code:$c, log_tail:$l}')
  posted=0
  for _ in $(seq 1 60); do  # 최대 ~180s
    if curl -sf --retry 3 --retry-connrefused \
      -X POST "$REINS_API_URL/api/deploy/${id}/result" "${AUTH[@]}" \
      -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1; then
      posted=1
      break
    fi
    sleep 3
  done
  [[ $posted -eq 0 ]] && echo "[agent] WARN: result post failed for job #${id} after retries (api down?)"
done
