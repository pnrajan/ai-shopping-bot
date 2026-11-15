#!/usr/bin/env bash
# Run every guardrail CI runs, in the same order. Exit non-zero on first failure.
#
#   bash scripts/check.sh                 # full run
#   bash scripts/check.sh -k refine -x    # extra args are passed to pytest only
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$VENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

step() { printf '\n==> %s\n' "$*"; "$@"; }

step ruff check .
step ruff format --check .
step lint-imports
step vulture shopper --min-confidence 80
step bash scripts/check_root_clutter.sh
step bash scripts/check_model_names.sh
step pytest -q --cov=shopper --cov-fail-under=80 "$@"

printf '\nAll checks passed.\n'
