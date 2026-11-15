#!/usr/bin/env bash
# One-time local setup: virtualenv, dependencies, .env from template.
#
#   bash scripts/setup.sh            # runtime deps only
#   bash scripts/setup.sh --dev      # plus test and lint tools
#
# Safe to re-run. Never touches an existing .env.
set -euo pipefail
cd "$(dirname "$0")/.."

DEV=0
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

need_version="3.11"
have_version="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
if [ "$(printf '%s\n%s\n' "$need_version" "$have_version" | sort -V | head -1)" != "$need_version" ]; then
  echo "Python >= $need_version required, found $have_version ($PYTHON). Set PYTHON=/path/to/python3.11+." >&2
  exit 1
fi

if [ ! -d "$VENV" ]; then
  echo "==> creating $VENV with $PYTHON $have_version"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> upgrading pip"
python -m pip install -q --upgrade pip

if [ "$DEV" = "1" ]; then
  echo "==> installing runtime + dev dependencies"
  pip install -q -e ".[dev]"
else
  echo "==> installing runtime dependencies"
  pip install -q -r requirements.txt
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> created .env from .env.example (offline fake mode). Edit it to go live."
else
  echo "==> .env exists, left untouched"
fi

cat <<MSG

Setup complete.
  Activate:  source $VENV/bin/activate
  Run:       bash scripts/run.sh
  Checks:    bash scripts/check.sh      (requires --dev)
MSG
