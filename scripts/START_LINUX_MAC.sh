#!/usr/bin/env bash
# Chay backend + frontend; thu muc chinh la thu muc goc du an.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" -m uvicorn backend.main:app --reload
