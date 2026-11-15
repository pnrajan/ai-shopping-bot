from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_chat_echoes_request():
    payload = {
        "recent_turn": "I need a laptop",
        "history": [
            {"role": "user", "message": "Hello"},
            {"role": "assistant", "message": "Hi!"},
        ],
        "conversation_id": "session-1",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "session-1"
    assert body["recent_turn"] == "I need a laptop"
    assert body["history_length"] == 2


def test_chat_empty_history():
    payload = {"recent_turn": "Hi", "history": [], "conversation_id": "s"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    assert response.json()["history_length"] == 0


def test_chat_missing_field_rejected():
    response = client.post("/chat", json={"recent_turn": "Hi"})
    assert response.status_code == 422
