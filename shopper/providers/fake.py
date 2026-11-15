"""Deterministic catalog for tests and offline runs."""

from __future__ import annotations

import hashlib

from shopper.contracts.product import Product, ProviderResults

_TIERS = ["Pro", "Lite", "Max", "Mini", "Plus"]
_BRANDS = ["Acme", "Northwind", "Contoso", "Globex", "Initech", "Umbrella"]


class FakeProvider:
    name = "fake"

    def search(
        self, query: str, *, category: str | None = None, limit: int = 10, timeout_s: float = 8.0
    ) -> ProviderResults:
        seed = int(hashlib.sha256(query.lower().encode()).hexdigest()[:8], 16)
        products = []
        for i in range(limit):
            n = (seed + i * 7919) % 10_000
            products.append(
                Product(
                    id=f"fake-{n}",
                    title=f"{query.title()} {_TIERS[i % 5]} {n % 100}",
                    price=round(20 + (n % 1500) * (1 + i / 10), 2),
                    rating=round(3.0 + (n % 20) / 10, 1),
                    total_ratings=100 + n % 5000,
                    brand=_BRANDS[(seed + i) % len(_BRANDS)],
                    url=f"https://example.com/p/{n}",
                    provider=self.name,
                    description=f"A {query.lower()} with feature set {i + 1}. USB-C, wireless.",
                    category=category or "",
                    in_stock=i % 4 != 3,
                )
            )
        return ProviderResults(provider=self.name, query=query, products=products, latency_ms=1)
