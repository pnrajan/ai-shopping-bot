"""Full pipeline through the HTTP layer with FakeLLM and a counting FakeProvider. No network."""


def _chat(client, turn, cid="c1", history=None):
    r = client.post(
        "/chat", json={"recent_turn": turn, "history": history or [], "conversation_id": cid}
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_search_returns_products_with_two_llm_calls(client, services):
    body = _chat(client, "laptop for video editing under $1500")
    assert body["data_type"] == "products" and body["data_count"] > 0
    assert all(p["price"] <= 1500 for p in body["data"])
    assert body["metadata"]["llm_calls"] == 2
    assert body["metadata"]["plan"] == ["product_search"]
    assert services.provider.calls == 1


def test_refinement_filters_without_new_search(client, services):
    first = _chat(client, "wireless headphones", cid="r1")
    before = services.provider.calls
    second = _chat(client, "which of these are under $300?", cid="r1")
    assert services.provider.calls == before
    assert second["metadata"]["note"] == "refinement"
    assert second["metadata"]["llm_calls"] <= 1
    assert 0 < second["data_count"] <= first["data_count"]
    assert all(p["price"] <= 300 for p in second["data"])


def test_repeat_query_hits_cache(client, services):
    _chat(client, "camping tent", cid="a")
    body = _chat(client, "camping tent", cid="b")
    assert body["metadata"]["from_cache"] is True
    assert services.provider.calls == 1


def test_comparison_returns_two_products_and_table(client):
    body = _chat(client, "sony wh-1000xm5 vs bose qc45")
    assert body["data_count"] == 2
    assert "|" in body["response"]
    assert body["metadata"]["llm_calls"] <= 4


def test_clarification_once_then_proceeds(client):
    first = _chat(client, "I want to buy something", cid="k")
    assert first["data_type"] == "clarification" and first["clarification_questions"]
    second = _chat(client, "I want to buy something", cid="k")
    assert second["data_type"] != "clarification"


def test_essentials_and_rationale_enrich(client):
    body = _chat(client, "what do I need for camping? recommend under $100")
    assert "Must have" in body["response"]
    assert body["metadata"]["llm_calls"] <= 4


def test_validation_error(client):
    r = client.post("/chat", json={"recent_turn": "x"})
    assert r.status_code == 422


def test_direct_product_search(client):
    r = client.get("/products/search", params={"q": "tent", "limit": 3})
    assert r.status_code == 200 and len(r.json()) == 3


def test_api_key_and_rate_limit(settings, services):
    from fastapi.testclient import TestClient

    from shopper.api.app import create_app
    from shopper.settings import Settings

    s = Settings(
        _env_file=None, llm="fake", catalog="fake", api_key="secret", rate_limit_per_minute=2
    )
    with TestClient(create_app(s, services)) as c:
        assert c.get("/products/search", params={"q": "t"}).status_code == 401
        h = {"X-API-Key": "secret"}
        assert c.get("/products/search", params={"q": "t"}, headers=h).status_code == 200
        assert c.get("/products/search", params={"q": "t"}, headers=h).status_code == 200
        assert c.get("/products/search", params={"q": "t"}, headers=h).status_code == 429
