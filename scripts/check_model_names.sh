#!/usr/bin/env bash
# Fail if a model name literal appears anywhere in ai_shopping_bot/ other than settings.py.
set -euo pipefail
cd "$(dirname "$0")/.."

hits=$(grep -rnE --include='*.py' 'gpt-[0-9]|claude-[0-9a-z]|Qwen[0-9/]|gemini-|llama-' ai_shopping_bot \
  | grep -v 'ai_shopping_bot/settings.py' | grep -v 'ai_shopping_bot/llm/client.py:.*#' || true)
if [ -n "$hits" ]; then
  echo "model name literals outside settings.py:"; echo "$hits"; exit 1
fi
