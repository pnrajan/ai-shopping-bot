#!/usr/bin/env bash
# Launch the API.
#
#   bash scripts/run.sh              # production-style, single worker
#   bash scripts/run.sh --dev        # auto-reload on code changes
#   bash scripts/run.sh --workers 4  # multiple workers (needs SHOPBOT_SESSION_STORE=sqlite, see docs/DEPLOYMENT.md)
#
# Reads .env if present. Host and port come from SHOPBOT_HOST / SHOPBOT_PORT (default 127.0.0.1:8000).
set -euo pipefail
cd "$(dirname "$0")/.."

RELOAD=0
WORKERS=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dev|--reload) RELOAD=1 ;;
    --workers=*) WORKERS="${1#--workers=}"; WORKERS_SET=1 ;;
    --workers)
      [ $# -ge 2 ] || { echo "--workers needs a positive integer" >&2; exit 2; }
      shift; WORKERS="$1"; WORKERS_SET=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "${WORKERS_SET:-0}" = "1" ] && ! [[ "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
  echo "--workers needs a positive integer" >&2; exit 2
fi
if [ "$RELOAD" = "1" ] && [ "${WORKERS_SET:-0}" = "1" ]; then
  echo "--dev (reload) runs a single process; it cannot be combined with --workers" >&2; exit 2
fi

VENV="${VENV:-.venv}"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$VENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

if ! python -c 'import uvicorn' 2>/dev/null; then
  echo "uvicorn not installed. Run: bash scripts/setup.sh" >&2
  exit 1
fi

# Load .env without clobbering variables already set in the environment.
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [ -z "${!key+x}" ]; then export "$key=$val"; fi
  done < .env
fi

HOST="${SHOPBOT_HOST:-127.0.0.1}"
PORT="${SHOPBOT_PORT:-8000}"

args=(main:app --host "$HOST" --port "$PORT")
if [ "$RELOAD" = "1" ]; then
  args+=(--reload --reload-dir ai_shopping_bot --reload-dir main.py)
  echo "==> dev server with reload on http://$HOST:$PORT  (docs at /docs)"
else
  args+=(--workers "$WORKERS")
  if [ "$WORKERS" -gt 1 ] && [ "${SHOPBOT_SESSION_STORE:-memory}" != "sqlite" ]; then
    echo "WARNING: $WORKERS workers with SHOPBOT_SESSION_STORE=${SHOPBOT_SESSION_STORE:-memory}. Sessions are per" >&2
    echo "         process, so refinement turns may miss. Set SHOPBOT_SESSION_STORE=sqlite (docs/DEPLOYMENT.md)." >&2
  fi
  echo "==> serving on http://$HOST:$PORT with $WORKERS worker(s)  (docs at /docs)"
fi
echo "    mode: llm=${SHOPBOT_LLM:-fake} catalog=${SHOPBOT_CATALOG:-fake}"

exec python -m uvicorn "${args[@]}"
