#!/usr/bin/env bash
# 보드 LLM 서버를 127.0.0.1:8090 으로 띄운다 (포그라운드. 백그라운드는 scripts/board/start_all.sh, 자동 실행은 systemd).
# 표준 라이브러리만 쓰므로 시스템 python3 로 충분하다. sudo 불필요 (클럭 고정 안 함).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL="${LOGION_RKLLM_MODEL:-$HOME/rkllm/logion/logion-delivery_w8a8_opt1_cal450.rkllm}"
LIB="${LOGION_RKLLM_LIB:-$HOME/rkllm/logion/demo_Linux_aarch64/lib/librkllmrt.so}"
PORT="${LOGION_LLM_PORT:-8090}"

for f in "$MODEL" "$LIB"; do
  [ -f "$f" ] || { echo "[start_llm] 파일 없음: $f" >&2; exit 1; }
done
ulimit -n 102400 2>/dev/null || true
exec python3 -u "$HERE/logion_server.py" --model "$MODEL" --lib "$LIB" --port "$PORT" --max_context 256
