"""Price and availability tracking shapes."""

from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """One sighting of a product at a provider."""

    provider: str
    product_id: str
    title: str = ""
    url: str = ""
    price: float | None = None
    currency: str = "USD"
    in_stock: bool | None = None
    query: str = Field("", description="Search that surfaced it; used to re-check")
    observed_at: float = Field(default_factory=time.time)


class Watch(BaseModel):
    """A product a client wants monitored."""

    id: int = 0
    provider: str
    product_id: str
    title: str = ""
    query: str = Field("", description="Search to re-run when checking. Falls back to title")
    target_price: float | None = Field(None, description="Alert when price drops to or below")
    created_at: float = Field(default_factory=time.time)


class WatchCreate(BaseModel):
    provider: str = Field(..., min_length=1, max_length=64)
    product_id: str = Field(..., min_length=1, max_length=256)
    title: str = Field("", max_length=512)
    query: str = Field("", max_length=512)
    target_price: float | None = Field(None, ge=0)


class AlertKind(StrEnum):
    PRICE_DROP = "price_drop"
    PRICE_RISE = "price_rise"
    BACK_IN_STOCK = "back_in_stock"
    OUT_OF_STOCK = "out_of_stock"
    TARGET_REACHED = "target_reached"


class Alert(BaseModel):
    kind: AlertKind
    provider: str
    product_id: str
    title: str = ""
    previous: Observation | None = None
    current: Observation
    watch_id: int | None = None


class PriceStats(BaseModel):
    provider: str
    product_id: str
    title: str = ""
    observations: int = 0
    current_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    in_stock: bool | None = None
    availability_ratio: float | None = Field(
        None, description="Share of observations that were in stock"
    )
    first_seen: float | None = None
    last_seen: float | None = None


class ProductHistory(BaseModel):
    stats: PriceStats
    history: list[Observation] = []
    alerts: list[Alert] = []
