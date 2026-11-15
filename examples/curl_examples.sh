#!/usr/bin/env bash
# Example requests against a locally running Personal Shopper API.
# Start the server first: python main.py
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "== New conversation =="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "recent_turn": "I need help finding a good smartphone under $500",
    "history": [],
    "conversation_id": "session-001"
  }'
echo

echo "== Follow-up with history =="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "recent_turn": "Prefer Android",
    "history": [
      {"role": "user", "message": "I need help finding a good smartphone under $500"},
      {"role": "assistant", "message": "Chat request received"}
    ],
    "conversation_id": "session-001"
  }'
echo
