"""Lexical relevance between a query and a product. Cheap on purpose; a reranker is a later
extra."""

from __future__ import annotations

import re

from shopper.contracts.product import Product

_STOP = {"a", "an", "the", "for", "with", "and", "or", "of", "to", "in", "on", "under", "best"}
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1}


def score(query: str, product: Product) -> float:
    q = tokens(query)
    if not q:
        return 0.5
    title = tokens(product.title)
    rest = tokens(product.text())
    in_title = len(q & title) / len(q)
    in_any = len(q & rest) / len(q)
    return round(min(1.0, 0.7 * in_title + 0.3 * in_any), 3)


def rank(query: str, products: list[Product]) -> list[Product]:
    scored = [p.model_copy(update={"relevance": score(query, p)}) for p in products]
    return sorted(scored, key=lambda p: (p.relevance, p.rating or 0), reverse=True)
