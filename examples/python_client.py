"""Minimal Python client for the Personal Shopper API.

Usage:
    pip install httpx2
    python examples/python_client.py
"""

import httpx2 as httpx

BASE_URL = "http://localhost:8000"


def chat(recent_turn: str, history: list[dict], conversation_id: str) -> dict:
    response = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "recent_turn": recent_turn,
            "history": history,
            "conversation_id": conversation_id,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    history: list[dict] = []
    conversation_id = "session-python-001"

    for turn in ["I need wireless headphones for the gym", "Budget is $150"]:
        reply = chat(turn, history, conversation_id)
        print(reply)
        history.append({"role": "user", "message": turn})
        history.append({"role": "assistant", "message": reply["message"]})
