"""Overlay the latest known price and stock onto products before they are returned.

Ported from the AvailabilityDB enrichment service. Applied to cached search results, which
can be up to the cache TTL old, so a newer sighting from a watch re-check or a later search
wins. Fresh provider results are already the newest truth and are not touched.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.tracking.store import AvailabilityStore


@dataclass
class EnrichResult:
    products: list[Product]
    looked_up: int = 0
    hits: int = 0
    changed: int = 0
    dropped: int = 0


def enrich(
    products: list[Product],
    store: AvailabilityStore,
    *,
    newer_than: float = 0.0,
    drop_unavailable: bool = False,
) -> EnrichResult:
    """Return copies of ``products`` with price, stock, and url from the tracked item.

    Only items updated after ``newer_than`` are applied, so callers can pass the time the
    cached result was produced. Products with no identity are passed through unchanged.
    """
    res = EnrichResult(products=[])
    for p in products:
        if not p.provider or not p.id:
            res.products.append(p)
            continue
        res.looked_up += 1
        item = store.item(p.provider, p.id)
        if item is None or item.updated_at <= newer_than:
            res.products.append(p)
            continue
        res.hits += 1
        if drop_unavailable and item.in_stock is False:
            res.dropped += 1
            continue
        changed = (item.price is not None and item.price != p.price) or (
            item.in_stock is not None and item.in_stock != p.in_stock
        )
        if changed:
            res.changed += 1
            res.products.append(
                p.model_copy(
                    update={
                        "price": item.price if item.price is not None else p.price,
                        "in_stock": item.in_stock if item.in_stock is not None else p.in_stock,
                        "url": item.url or p.url,
                    }
                )
            )
        else:
            res.products.append(p)
    return res
