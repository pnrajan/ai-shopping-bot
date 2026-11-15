#!/usr/bin/env bash
# Fail if a model name literal appears anywhere in shopper/ other than settings.py.
set -euo pipefail
cd "$(dirname "$0")/.."

hits=$(grep -rnE --include='*.py' 'gpt-[0-9]|claude-[0-9a-z]|Qwen[0-9/]|gemini-|llama-' shopper \
  | grep -v 'shopper/settings.py' | grep -v 'shopper/llm/client.py:.*#' || true)
if [ -n "$hits" ]; then
  echo "model name literals outside settings.py:"; echo "$hits"; exit 1
fi
