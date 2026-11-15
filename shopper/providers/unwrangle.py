"""UnWrangle catalog API (documented, keyed; not a scraper).

Default endpoint is UnWrangle's getter API for Amazon search. Override with ``UNWRANGLE_SEARCH_URL``
if your plan uses a different platform or host. The key is read from settings, never from code.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from shopper.contracts.product import Product, ProviderResults
from shopper.logging import get_logger, log_event

log = get_logger("providers.unwrangle")

DEFAULT_URL = "https://data.unwrangle.com/api/getter/"


class UnWrangleProvider:
    name = "unwrangle"

    def __init__(
        self,
        api_key: str,
        *,
        url: str = DEFAULT_URL,
        platform: str = "amazon_search",
        country: str = "us",
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ValueError("UnWrangleProvider needs an API key")
        self._key = api_key
        self._url = url
        self._platform = platform
        self._country = country
        self._client = client or httpx.Client()

    def search(
        self, query: str, *, category: str | None = None, limit: int = 10, timeout_s: float = 8.0
    ) -> ProviderResults:
        params = {
            "platform": self._platform,
            "search": query,
            "page": 1,
            "country_code": self._country,
            "api_key": self._key,
        }
        started = time.perf_counter()
        try:
            r = self._client.get(self._url, params=params, timeout=timeout_s)
            r.raise_for_status()
            payload = r.json()
        except httpx.HTTPError as e:
            ms = int((time.perf_counter() - started) * 1000)
            log_event(log, "provider.error", provider=self.name, error=e.__class__.__name__, ms=ms)
            return ProviderResults(
                provider=self.name, query=query, latency_ms=ms, error=e.__class__.__name__
            )
        ms = int((time.perf_counter() - started) * 1000)
        products = [p for p in (_parse(item, category) for item in payload.get("results", [])) if p]
        log_event(log, "provider.search", provider=self.name, count=len(products), ms=ms)
        return ProviderResults(
            provider=self.name, query=query, products=products[:limit], latency_ms=ms
        )


def _parse(d: dict[str, Any], category: str | None) -> Product | None:
    title = d.get("name") or d.get("title")
    if not title:
        return None
    return Product(
        id=str(d.get("asin") or d.get("id") or ""),
        title=str(title),
        price=_to_float(d.get("price")),
        currency=str(d.get("currency") or "USD"),
        rating=_to_float(d.get("rating")),
        total_ratings=_to_int(d.get("total_ratings") or d.get("total_reviews")),
        brand=str(d.get("brand") or ""),
        url=str(d.get("url") or ""),
        provider="unwrangle",
        description=str(d.get("description") or ""),
        category=category or "",
        thumbnail=d.get("thumbnail") or d.get("image_url"),
        in_stock=d.get("in_stock"),
        model_no=str(d.get("model_no") or ""),
    )


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return None
