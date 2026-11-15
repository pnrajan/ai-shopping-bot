"""Provider protocol. Implementations must not scrape sites against their terms of service."""

from __future__ import annotations

from typing import Protocol

from ai_shopping_bot.contracts.product import ProviderResults


class CatalogProvider(Protocol):
    name: str

    def search(
        self, query: str, *, category: str | None = None, limit: int = 10, timeout_s: float = 8.0
    ) -> ProviderResults: ...
