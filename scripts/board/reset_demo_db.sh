#!/usr/bin/env bash
# 시연용 DB 를 "새 하루" 상태로 되돌린다 (완료 0, 이상 보고 0, 대화 기록 0).
# 지금 DB 는 지우지 않고 logs/db_backup_<시각>/ 로 옮긴다. 백엔드를 다시 켜면 seed 가 기준 정보와 오늘 운행을 새로 만든다.
#   bash scripts/board/reset_demo_db.sh
# systemd(logion-backend)로 돌고 있으면 sudo systemctl 로, start_all.sh 로 켰으면 백엔드만 끄고 다시 켠다 (LLM 서버는 그대로).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOGS="$REPO/logs"; mkdir -p "$LOGS"
DB="${LOGION_DB:-$REPO/backend/data/logion.db}"
BK="$LOGS/db_backup_$(date +%Y%m%d_%H%M%S)"
PORT="${LOGION_BACKEND_PORT:-8000}"

if systemctl is-active --quiet logion-backend 2>/dev/null; then
  MODE=systemd
  sudo systemctl stop logion-backend
else
  MODE=script
  if [ -f "$LOGS/backend.pid" ] && kill -0 "$(cat "$LOGS/backend.pid")" 2>/dev/null; then
    p="$(cat "$LOGS/backend.pid")"; kill "$p"
    for _ in $(seq 1 15); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    kill -0 "$p" 2>/dev/null && kill -9 "$p"
    echo "백엔드 종료 (pid $p)"
  fi
  : > "$LOGS/backend.pid"
fi

mkdir -p "$BK"
for f in "$DB" "$DB-wal" "$DB-shm"; do
  [ -f "$f" ] && mv "$f" "$BK/"
done
echo "이전 DB 를 옮겨 둠: $BK"

if [ "$MODE" = systemd ]; then
  sudo systemctl start logion-backend
else
  bash "$REPO/scripts/board/start_all.sh" | tail -1
fi

for _ in $(seq 1 60); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/health" && break; sleep 1; done
curl -s "http://127.0.0.1:$PORT/api/routes/today" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("오늘 운행", d["service_date"], "· 완료", d["summary"]["done"], "/", d["summary"]["total"],
      "·", ", ".join(s["store"]["short_name"] for s in d["stops"]))'
