#!/usr/bin/env bash
# LLM 서버 → 백엔드 순서로 백그라운드 실행. 로그와 pid 는 ~/LogiOn/logs/
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOGS="$REPO/logs"; mkdir -p "$LOGS"
LLM_PORT="${LOGION_LLM_PORT:-8090}"; BE_PORT="${LOGION_BACKEND_PORT:-8000}"

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

wait_http() {  # url 초
  for _ in $(seq 1 "$2"); do curl -sf -o /dev/null "$1" && return 0; sleep 1; done; return 1
}

if alive "$LOGS/llm.pid"; then
  echo "LLM 서버 이미 실행 중 (pid $(cat "$LOGS/llm.pid"))"
else
  nohup "$REPO/rkllm/server/start_llm.sh" >> "$LOGS/llm_server.log" 2>&1 < /dev/null &
  echo $! > "$LOGS/llm.pid"
  echo "LLM 서버 시작 (pid $!), 모델 로딩 대기..."
fi
if wait_http "http://127.0.0.1:$LLM_PORT/health" 90; then
  echo "LLM 서버 준비: $(curl -s http://127.0.0.1:$LLM_PORT/health)"
else
  echo "LLM 서버가 90초 안에 뜨지 않음. $LOGS/llm_server.log 확인" >&2; exit 1
fi

if alive "$LOGS/backend.pid"; then
  echo "백엔드 이미 실행 중 (pid $(cat "$LOGS/backend.pid"))"
else
  nohup "$REPO/scripts/board/start_backend.sh" >> "$LOGS/backend.log" 2>&1 < /dev/null &
  echo $! > "$LOGS/backend.pid"
  echo "백엔드 시작 (pid $!)"
fi
if wait_http "http://127.0.0.1:$BE_PORT/api/health" 60; then
  echo "백엔드 준비: $(curl -s http://127.0.0.1:$BE_PORT/api/assistant/status)"
else
  echo "백엔드가 60초 안에 뜨지 않음. $LOGS/backend.log 확인" >&2; exit 1
fi
