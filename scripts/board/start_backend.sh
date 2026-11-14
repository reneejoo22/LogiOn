#!/usr/bin/env bash
# 보드 백엔드(FastAPI)를 0.0.0.0:8000 으로 띄운다 (포그라운드). 파이프라인은 보드 LLM 서버(rkllm 모드)를 쓴다.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="${LOGION_VENV:-$REPO/.venv-board}"
PORT="${LOGION_BACKEND_PORT:-8000}"

export LOGION_LLM_BACKEND="${LOGION_LLM_BACKEND:-rkllm}"
export LOGION_LLM_URL="${LOGION_LLM_URL:-http://127.0.0.1:8090}"
export PYTHONUNBUFFERED=1
[ -x "$VENV/bin/python" ] || { echo "[start_backend] $VENV 없음. scripts/board/setup_venv.sh 먼저 실행" >&2; exit 1; }
cd "$REPO/backend"
exec "$VENV/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
