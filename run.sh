#!/usr/bin/env bash
# 로컬 실행 헬퍼: venv 만들고 의존성 깔고 서버 띄운다.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

export RUNSTOP_DATA_DIR="${RUNSTOP_DATA_DIR:-$PWD/datasets}"
export RUNSTOP_GRAPHML="${RUNSTOP_GRAPHML:-$PWD/algo/data/서울_보행네트워크.graphml}"

exec ./.venv/bin/uvicorn app.server:app --host 0.0.0.0 --port "${PORT:-8000}"
