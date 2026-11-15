"""Product shapes shared by providers, search, and the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str = ""
    title: str
    price: float | None = Field(None, description="Numeric price in ``currency``")
    currency: str = "USD"
    rating: float | None = None
    total_ratings: int | None = None
    brand: str = ""
    url: str = ""
    provider: str = ""
    description: str = ""
    category: str = ""
    thumbnail: str | None = None
    in_stock: bool | None = None
    model_no: str = ""
    relevance: float = Field(0.0, ge=0.0, le=1.0)

    def text(self) -> str:
        return " ".join(p for p in (self.title, self.brand, self.description, self.category) if p)


class ProviderResults(BaseModel):
    provider: str
    query: str
    products: list[Product] = Field(default_factory=list)
    latency_ms: int = 0
    error: str | None = None
