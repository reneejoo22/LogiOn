#!/usr/bin/env bash
# 보드에 ~/LogiOn/.venv-board 를 만들고 백엔드+파이프라인 의존성만 설치한다 (sudo 없이, 시스템 파이썬은 건드리지 않음).
# 보드 Ubuntu 22.04 에는 python3.10-venv(ensurepip)가 없어서 --without-pip 로 만든 뒤 get-pip.py 로 venv 안에만 pip 를 넣는다.
# (sudo 를 쓸 수 있으면 'sudo apt install python3.10-venv' 후 일반 python3 -m venv 로 만들어도 된다.)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="${LOGION_VENV:-$REPO/.venv-board}"

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv --without-pip "$VENV"
fi
if ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$VENV/get-pip.py"
  "$VENV/bin/python" "$VENV/get-pip.py" --no-warn-script-location
fi
"$VENV/bin/python" -m pip install --no-warn-script-location -r "$REPO/scripts/board/requirements-board.txt"
"$VENV/bin/python" -c "import fastapi, uvicorn, sys; print('ok', sys.executable, fastapi.__version__, uvicorn.__version__)"
