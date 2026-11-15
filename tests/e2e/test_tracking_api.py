from __future__ import annotations

from fastapi.testclient import TestClient

from ai_shopping_bot.api.app import create_app
from ai_shopping_bot.api.wiring import build_services
from ai_shopping_bot.settings import Settings


def test_search_records_history_and_watch_lifecycle(client: TestClient):
    products = client.get("/products/search", params={"q": "gaming laptop", "limit": 3}).json()
    pid = products[0]["id"]
    r = client.get(f"/products/fake/{pid}/history")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["observations"] == 1
    assert body["stats"]["current_price"] == products[0]["price"]
    assert body["history"][0]["provider"] == "fake"

    r = client.post("/watches", json={"provider": "fake", "product_id": pid, "target_price": 1})
    assert r.status_code == 201
    wid = r.json()["id"]
    assert [w["id"] for w in client.get("/watches").json()] == [wid]

    # the fake catalog is deterministic, so a re-check records a sighting but no alert
    r = client.post("/watches/check")
    assert r.status_code == 200 and r.json() == []
    assert client.get(f"/products/fake/{pid}/history").json()["stats"]["observations"] == 2
    assert client.get("/alerts").json() == []

    assert client.delete(f"/watches/{wid}").status_code == 204
    assert client.delete(f"/watches/{wid}").status_code == 404


def test_chat_turn_records_products_seen(client: TestClient):
    r = client.post(
        "/chat", json={"recent_turn": "wireless mouse", "history": [], "conversation_id": "t1"}
    )
    first = r.json()["data"][0]
    hist = client.get(f"/products/{first['provider']}/{first['id']}/history").json()
    assert hist["stats"]["observations"] >= 1


def test_unknown_product_is_404(client: TestClient):
    assert client.get("/products/fake/nothing/history").status_code == 404


def test_tracking_off_hides_endpoints():
    settings = Settings(_env_file=None, llm="fake", catalog="fake", tracking="off")
    app = create_app(settings, build_services(settings))
    with TestClient(app) as c:
        assert c.get("/watches").status_code == 404
        assert c.post("/watches/check").status_code == 404
        assert c.get("/health").status_code == 200
