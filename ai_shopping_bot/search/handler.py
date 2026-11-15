"""Search orchestration: provider calls, dedupe, rank, filter. Shared by the chat tool and REST."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ai_shopping_bot.cache.semantic import SemanticCache
from ai_shopping_bot.contracts.product import Product, ProviderResults
from ai_shopping_bot.contracts.understanding import QueryUnderstanding
from ai_shopping_bot.logging import get_logger, log_event
from ai_shopping_bot.providers.base import CatalogProvider
from ai_shopping_bot.search import filters, relevance

log = get_logger("search")


class SearchHandler:
    def __init__(
        self,
        provider: CatalogProvider,
        *,
        cache: SemanticCache | None = None,
        timeout_s: float = 8.0,
        default_limit: int = 10,
    ):
        self._provider = provider
        self._cache = cache
        self._timeout = timeout_s
        self._limit = default_limit

    def search(
        self, qu: QueryUnderstanding, *, limit: int | None = None
    ) -> tuple[list[Product], dict]:
        limit = limit or self._limit
        queries = qu.search_queries or [qu.canonical_query]
        key = SemanticCache.key(queries, qu.category)
        cached = self._cache.get(key) if self._cache else None
        if cached is not None:
            products = [Product.model_validate(p) for p in cached]
            return self._finish(qu, products, limit, from_cache=True, provider_calls=0)
        results = self._fetch(queries, qu.category, limit)
        merged = _dedupe([p for r in results for p in r.products])
        if self._cache and merged:
            self._cache.put(key, [p.model_dump() for p in merged])
        return self._finish(qu, merged, limit, from_cache=False, provider_calls=len(results))

    def _fetch(self, queries: list[str], category: str | None, limit: int) -> list[ProviderResults]:
        per_query = max(limit, 10)
        with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
            return list(
                pool.map(
                    lambda q: self._provider.search(
                        q, category=category, limit=per_query, timeout_s=self._timeout
                    ),
                    queries,
                )
            )

    def _finish(
        self,
        qu: QueryUnderstanding,
        products: list[Product],
        limit: int,
        *,
        from_cache: bool,
        provider_calls: int,
    ) -> tuple[list[Product], dict]:
        ranked = relevance.rank(qu.canonical_query, products)
        filtered = filters.apply_understanding(ranked, qu)[:limit]
        meta = {
            "from_cache": from_cache,
            "provider_calls": provider_calls,
            "candidates": len(products),
            "returned": len(filtered),
        }
        log_event(log, "search.done", **meta)
        return filtered, meta


def _dedupe(products: list[Product]) -> list[Product]:
    seen: set[str] = set()
    out = []
    for p in products:
        k = p.id or p.url or p.title.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out
