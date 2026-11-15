import httpx
import pytest
import respx

from shopper.providers.fake import FakeProvider
from shopper.providers.unwrangle import DEFAULT_URL, UnWrangleProvider


def test_fake_provider_is_deterministic():
    a = FakeProvider().search("tent", limit=3)
    b = FakeProvider().search("tent", limit=3)
    assert [p.id for p in a.products] == [p.id for p in b.products]
    assert len(a.products) == 3


@respx.mock
def test_unwrangle_parses_results_and_hides_key():
    route = respx.get(DEFAULT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "asin": "B1",
                        "name": "Tent 2P",
                        "price": "$89.99",
                        "rating": "4.5",
                        "total_ratings": "1,234",
                        "brand": "Acme",
                        "url": "https://a/b",
                        "in_stock": True,
                    },
                    {"asin": "B2"},
                ]
            },
        )
    )
    p = UnWrangleProvider("secret-key")
    r = p.search("tent", limit=5)
    assert r.error is None and len(r.products) == 1
    prod = r.products[0]
    assert prod.price == 89.99 and prod.total_ratings == 1234 and prod.provider == "unwrangle"
    assert route.calls[0].request.url.params["api_key"] == "secret-key"
    assert "secret-key" not in repr(r)


@respx.mock
def test_unwrangle_http_error_is_soft():
    respx.get(DEFAULT_URL).mock(return_value=httpx.Response(500))
    r = UnWrangleProvider("k").search("tent")
    assert r.products == [] and r.error == "HTTPStatusError"


def test_unwrangle_requires_key():
    with pytest.raises(ValueError):
        UnWrangleProvider("")
