#!/usr/bin/env bash
# Local Definition of Done (AGENTS.md) plus the demo, in one command.
#
#   scripts/check.sh                      # ruff, format, mypy, pytest
#   scripts/check.sh --demo               # ...and then the M1 demo
#   scripts/check.sh -k round_trip        # extra args go to pytest
#
# Creates .venv and installs the dev extras on first run. Override the interpreter
# with PYTHON=python3.11 and the env directory with VENV=.venv311.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=${VENV:-.venv}
PYTHON=${PYTHON:-python3}
demo=0
if [ "${1:-}" = "--demo" ]; then
  demo=1
  shift
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "== creating $VENV =="
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install -q -e ".[dev]"
fi
PY="$VENV/bin/python"

echo "== ruff check =="
"$VENV/bin/ruff" check .
echo "== ruff format --check =="
"$VENV/bin/ruff" format --check .
echo "== mypy (strict) =="
"$VENV/bin/mypy"
echo "== pytest =="
"$VENV/bin/pytest" -q -rs "$@"

if [ "$demo" = 1 ]; then
  echo
  echo "== demo =="
  "$PY" scripts/demo.py
fi

echo
echo "OK"
