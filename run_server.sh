#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 scripts/bootstrap.py || true
if [ -x .venv/bin/python ]; then
  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
else
  echo "missing .venv/bin/python"
  exit 1
fi
