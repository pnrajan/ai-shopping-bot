#!/usr/bin/env bash
# Run every guardrail CI runs, in the same order. Exit non-zero on first failure.
#
#   bash scripts/check.sh                 # full run, same as CI
#   bash scripts/check.sh -k refine -x    # extra args go to pytest; coverage gate is skipped
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in -h|--help) sed -n '2,5p' "$0"; exit 0 ;; esac

VENV="${VENV:-.venv}"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$VENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

step() { printf '\n==> %s\n' "$*"; "$@"; }

step ruff check .
step ruff format --check .
step lint-imports
step vulture ai_shopping_bot --min-confidence 80
step bash scripts/check_root_clutter.sh
step bash scripts/check_model_names.sh
if [ $# -eq 0 ]; then
  step pytest -q --cov=ai_shopping_bot --cov-fail-under=80
else
  echo "(pytest args given: coverage gate skipped)"
  step pytest -q "$@"
fi

printf '\nAll checks passed.\n'
