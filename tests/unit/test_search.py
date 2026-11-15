from shopper.cache.semantic import InMemoryBackend, SemanticCache
from shopper.contracts.product import Product
from shopper.contracts.understanding import Attribute, QueryUnderstanding
from shopper.providers.fake import FakeProvider
from shopper.search import filters, relevance
from shopper.search.handler import SearchHandler


def _p(title, price, rating=4.0, brand="", desc=""):
    return Product(title=title, price=price, rating=rating, brand=brand, description=desc)


def test_relevance_prefers_title_matches():
    q = "gaming laptop"
    a = _p("Gaming Laptop 15", 999)
    b = _p("Office Chair", 99, desc="not a laptop")
    ranked = relevance.rank(q, [b, a])
    assert ranked[0].title == a.title
    assert ranked[0].relevance > ranked[1].relevance


def test_filters_skip_when_they_would_empty_the_list():
    items = [_p("A", 100), _p("B", 200)]
    qu = QueryUnderstanding(
        query="x", canonical_query="x", attributes=[Attribute(name="max_price", value="10")]
    )
    assert filters.apply_understanding(items, qu) == items


def test_filters_apply_price_and_brand():
    items = [_p("A", 100, brand="Acme"), _p("B", 200, brand="Acme"), _p("C", 50, brand="Zed")]
    qu = QueryUnderstanding(
        query="x",
        canonical_query="x",
        attributes=[
            Attribute(name="max_price", value="150"),
            Attribute(name="brand", value="acme"),
        ],
    )
    out = filters.apply_understanding(items, qu)
    assert [p.title for p in out] == ["A"]


def test_cache_key_normalizes_order_and_stopwords():
    assert SemanticCache.key(["the best Laptop for gaming"]) == SemanticCache.key(["gaming laptop"])


def test_cache_ttl_expiry(monkeypatch):
    backend = InMemoryBackend()
    cache = SemanticCache(backend, ttl_s=10)
    now = [1000.0]
    monkeypatch.setattr("shopper.cache.semantic.time.time", lambda: now[0])
    cache.put("k", [1])
    assert cache.get("k") == [1]
    now[0] += 11
    assert cache.get("k") is None
    assert cache.hits == 1 and cache.misses == 1


def test_handler_uses_cache_on_second_call():
    class Counting(FakeProvider):
        calls = 0

        def search(self, *a, **k):
            Counting.calls += 1
            return super().search(*a, **k)

    h = SearchHandler(Counting(), cache=SemanticCache())
    qu = QueryUnderstanding(
        query="headphones", canonical_query="headphones", search_queries=["headphones"]
    )
    _, m1 = h.search(qu)
    _, m2 = h.search(qu)
    assert m1["from_cache"] is False and m2["from_cache"] is True
    assert Counting.calls == 1
