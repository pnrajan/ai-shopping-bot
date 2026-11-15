"""Price and availability tracking shapes."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Annotated

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


class TrackedItem(BaseModel):
    """Current known state of one product at one provider. Ported from AvailabilityDB."""

    provider: str
    product_id: str
    title: str = ""
    url: str = ""
    price: float | None = None
    currency: str = "USD"
    in_stock: bool | None = None
    query: str = ""
    observations: int = 0
    first_seen: float = 0.0
    updated_at: float = 0.0

    def is_stale(self, after_s: float, now: float | None = None) -> bool:
        return ((now or time.time()) - self.updated_at) > after_s


class ItemRef(BaseModel):
    provider: str = Field(..., min_length=1, max_length=64)
    product_id: str = Field(..., min_length=1, max_length=256)


class BulkLookup(BaseModel):
    items: list[ItemRef] = Field(default_factory=list, max_length=200)
    urls: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(
        default_factory=list, max_length=200
    )


class BulkLookupResponse(BaseModel):
    found: list[TrackedItem] = []
    missing: list[str] = Field(default_factory=list, description="provider/product_id or url")


class TrackingStatus(BaseModel):
    enabled: bool
    store: str
    items: int = 0
    available: int = 0
    unavailable: int = 0
    unknown: int = 0
    stale: int = 0
    stale_after_s: float = 0
    watches: int = 0
    alerts: int = 0
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    last_updated: float | None = None
    monitor_interval_s: float = 0
    enrich_cached: bool = False


class RefreshSummary(BaseModel):
    """Result of re-checking tracked items against their providers."""

    candidates: int = 0
    checked: int = 0
    updated: int = 0
    changed: int = 0
    missed: int = 0
    alerts: list[Alert] = []
    duration_ms: int = 0
