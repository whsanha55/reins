#!/usr/bin/env bash
# deploy.sh — reins 빌드/serve. host agent 가 git 동기화(fetch/reset) 후 호출.
# model 2 deploy-as-code: 본 스크립트=프로젝트별 빌드(docker compose up). agent=공통 git 동기화.
# 호스트(jjong) 에서 docker compose up -d --build + health check 수행.
set -uo pipefail

cd "$(dirname "$0")"

echo "==> docker compose up -d --build"
docker compose up -d --build || { echo "==> FAIL: compose up"; exit 1; }

# health 대기(ui:21002 가 api:21001 로 프록시). 최대 ~60s.
echo "==> waiting for health..."
code=000
for _ in $(seq 1 30); do
  code=$(curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:21002/health 2>/dev/null || echo 000)
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "$code" != "200" ]]; then
  echo "==> FAIL: health timeout (last=$code)"
  docker compose logs --tail=40
  exit 1
fi

echo "==> Done. $(git rev-parse --short HEAD)"
