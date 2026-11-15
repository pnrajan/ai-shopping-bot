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


def test_tracking_status_items_bulk_and_refresh(client: TestClient):
    products = client.get("/products/search", params={"q": "espresso machine", "limit": 3}).json()
    st = client.get("/tracking/status").json()
    assert st["enabled"] and st["items"] >= 3 and st["store"] == "memory"
    items = client.get("/tracking/items", params={"in_stock": "true"}).json()
    assert all(i["in_stock"] for i in items)
    one = client.get(f"/tracking/items/fake/{products[0]['id']}").json()
    assert one["price"] == products[0]["price"] and one["query"] == "espresso machine"
    assert client.get("/tracking/items/fake/nope").status_code == 404
    r = client.post(
        "/tracking/items/bulk",
        json={
            "items": [
                {"provider": "fake", "product_id": products[1]["id"]},
                {"provider": "fake", "product_id": "zz"},
            ],
            "urls": [products[2]["url"], "https://example.com/none"],
        },
    ).json()
    assert len(r["found"]) == 2 and r["missing"] == ["fake/zz", "https://example.com/none"]
    r = client.post("/tracking/refresh", params={"stale_after_s": 0, "limit": 2}).json()
    assert r["candidates"] == 2 and r["checked"] == 2 and r["updated"] == 2


def test_cached_search_is_enriched_with_newer_tracked_state(client: TestClient, services):
    first = client.get("/products/search", params={"q": "standing desk", "limit": 2}).json()
    pid = first[0]["id"]
    # a later sighting (from a re-check, say) reports a lower price and no stock
    from ai_shopping_bot.contracts.tracking import Observation

    services.tracker.record_observation(
        Observation(
            provider="fake", product_id=pid, price=1.0, in_stock=False, title=first[0]["title"]
        )
    )
    again = client.get("/products/search", params={"q": "standing desk", "limit": 2}).json()
    hit = next(p for p in again if p["id"] == pid)
    assert hit["price"] == 1.0 and hit["in_stock"] is False


def test_refresh_and_history_reject_bad_bounds(client: TestClient):
    assert client.post("/tracking/refresh", params={"stale_after_s": -1}).status_code == 422
    assert client.post("/tracking/refresh", params={"limit": 0}).status_code == 422
    assert client.post("/tracking/refresh", params={"limit": -1}).status_code == 422
    assert client.get("/products/fake/x/history", params={"limit": 0}).status_code == 422
    assert client.post("/tracking/items/bulk", json={"urls": [""]}).status_code == 422
