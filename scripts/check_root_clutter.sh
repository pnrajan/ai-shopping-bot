#!/usr/bin/env bash
# Fail if the repo root grows loose scripts or tracked build artifacts.
set -euo pipefail
cd "$(dirname "$0")/.."

bad=0
for f in $(git ls-files -- '*.py' '*.sh' | grep -v '/' || true); do
  if [ "$f" != "main.py" ]; then echo "root clutter: $f"; bad=1; fi
done
for pat in 'htmlcov/' 'coverage.xml' '.coverage' '*.db' '__pycache__' '*.pyc'; do
  if git ls-files | grep -qE "^${pat//\*/.*}"; then echo "tracked artifact: $pat"; bad=1; fi
done
exit $bad
