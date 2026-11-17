#!/usr/bin/env bash
# start_all.sh 로 켠 백엔드와 LLM 서버를 끈다 (pid 파일 기준. 다른 프로세스는 건드리지 않음)
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOGS="$REPO/logs"

stop() {  # 이름 pid파일
  local f="$2"
  if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
    local p; p="$(cat "$f")"
    kill "$p"
    for _ in $(seq 1 15); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    kill -0 "$p" 2>/dev/null && kill -9 "$p"
    echo "$1 종료 (pid $p)"
  else
    echo "$1 실행 중 아님"
  fi
  : > "$f" 2>/dev/null || true
}
stop "백엔드" "$LOGS/backend.pid"
stop "LLM 서버" "$LOGS/llm.pid"
