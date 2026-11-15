"""Minimal client showing a search turn followed by a refinement turn.

Usage:
    python examples/python_client.py            # server on localhost:8000
    SHOPBOT_URL=http://host:port python examples/python_client.py
"""

from __future__ import annotations

import os

import httpx

BASE_URL = os.environ.get("SHOPBOT_URL", "http://localhost:8000")
API_KEY = os.environ.get("SHOPBOT_API_KEY")


def chat(turn: str, conversation_id: str) -> dict:
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    r = httpx.post(
        f"{BASE_URL}/chat",
        json={"recent_turn": turn, "history": [], "conversation_id": conversation_id},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    cid = "example-001"
    for turn in ["wireless headphones for the gym", "which of these are under $150?"]:
        reply = chat(turn, cid)
        print(f"> {turn}")
        print(reply["response"])
        for p in reply["data"][:3]:
            print(f"  - {p['title']}  ${p['price']}")
        print(f"  [{reply['metadata']['llm_calls']} LLM calls, {reply['data_count']} products]\n")
