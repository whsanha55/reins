#!/usr/bin/env bash
# reins 로컬 dev 실행기. backend(21001) + ui(21002).
# 이미 켜진 포트면 kill 후 재시작. Ctrl+C 로 둘 다 종료.
set -uo pipefail

cd "$(dirname "$0")"

BACKEND_PORT=21001
FRONTEND_PORT=21002
LOG_DIR="$PWD/.logs"
mkdir -p "$LOG_DIR"

# 포트 점유 프로세스 kill.
kill_port() {
  local pids
  pids="$(lsof -ti tcp:"$1" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "kill port $1 (pid: $(echo "$pids" | tr '\n' ' '))"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.3
  fi
}

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

(cd server && uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT") \
  > "$LOG_DIR/backend.log" 2>&1 &
BACK_PID=$!

(cd ui && npm run dev) \
  > "$LOG_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

cleanup() {
  kill -9 "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "backend  → http://localhost:$BACKEND_PORT  (pid $BACK_PID, log .logs/backend.log)"
echo "frontend → http://localhost:$FRONTEND_PORT  (pid $FRONT_PID, log .logs/frontend.log)"
echo "Ctrl+C 로 둘 다 종료.\n"

tail -f "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
