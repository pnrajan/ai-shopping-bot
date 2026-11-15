"""Attribute filters applied after ranking."""

from __future__ import annotations

from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.contracts.understanding import QueryUnderstanding


def by_max_price(products: list[Product], max_price: float) -> list[Product]:
    return [p for p in products if p.price is not None and p.price <= max_price]


def by_min_price(products: list[Product], min_price: float) -> list[Product]:
    return [p for p in products if p.price is not None and p.price >= min_price]


def by_min_rating(products: list[Product], min_rating: float) -> list[Product]:
    return [p for p in products if p.rating is not None and p.rating >= min_rating]


def by_brand(products: list[Product], brand: str) -> list[Product]:
    b = brand.lower()
    return [p for p in products if b in p.brand.lower() or b in p.title.lower()]


def by_features(products: list[Product], features: list[str]) -> list[Product]:
    wanted = [f.lower() for f in features if f.strip()]
    return [p for p in products if all(f in p.text().lower() for f in wanted)]


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit() or c == ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def apply_understanding(products: list[Product], qu: QueryUnderstanding) -> list[Product]:
    """Apply every filter the understanding stage extracted. Never returns empty when input was not:
    if a filter removes everything, that filter is skipped and the previous list kept."""
    out = products
    steps = (
        (qu.max_price(), by_max_price),
        (_parse_float(qu.attribute("min_price")), by_min_price),
        (_parse_float(qu.attribute("rating_min")), by_min_rating),
    )
    for value, fn in steps:
        if value is not None:
            narrowed = fn(out, value)
            out = narrowed or out
    brand = qu.attribute("brand")
    if brand:
        out = by_brand(out, brand) or out
    return out
