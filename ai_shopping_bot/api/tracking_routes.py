"""Price history, watches, and alerts. Mounted only when a tracker is configured."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ai_shopping_bot.api.wiring import Services
from ai_shopping_bot.contracts.tracking import (
    Alert,
    BulkLookup,
    BulkLookupResponse,
    ProductHistory,
    RefreshSummary,
    TrackedItem,
    TrackingStatus,
    Watch,
    WatchCreate,
)
from ai_shopping_bot.settings import Settings
from ai_shopping_bot.tracking import AvailabilityStore


def build_tracking_router(settings: Settings, guard: Callable, svc: Callable) -> APIRouter:
    router = APIRouter(dependencies=[Depends(guard)], tags=["tracking"])

    def tracker(s: Services = Depends(svc)) -> AvailabilityStore:
        if s.tracker is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "tracking is disabled")
        return s.tracker

    @router.get("/products/{provider}/{product_id}/history", response_model=ProductHistory)
    def product_history(
        provider: str,
        product_id: str,
        limit: int | None = Query(None, ge=1, le=1000),
        t: AvailabilityStore = Depends(tracker),
    ) -> ProductHistory:
        n = limit or settings.tracking_history_limit
        history = t.history(provider, product_id, n)
        if not history:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no observations for this product")
        alerts = [a for a in t.alerts(200) if a.provider == provider and a.product_id == product_id]
        return ProductHistory(stats=t.stats(provider, product_id), history=history, alerts=alerts)

    _watch_routes(router, tracker, svc)
    _item_routes(router, tracker, svc, settings)

    @router.get("/alerts", response_model=list[Alert])
    def list_alerts(limit: int = 50, t: AvailabilityStore = Depends(tracker)) -> list[Alert]:
        return t.alerts(max(1, min(limit, 500)))

    return router


def _watch_routes(router: APIRouter, tracker: Callable, svc: Callable) -> None:
    @router.get("/watches", response_model=list[Watch])
    def list_watches(t: AvailabilityStore = Depends(tracker)) -> list[Watch]:
        return t.watches()

    @router.post("/watches", response_model=Watch, status_code=status.HTTP_201_CREATED)
    def create_watch(body: WatchCreate, t: AvailabilityStore = Depends(tracker)) -> Watch:
        return t.add_watch(body)

    @router.post("/watches/check", response_model=list[Alert])
    def check_watches(s: Services = Depends(svc)) -> list[Alert]:
        if s.monitor is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "tracking is disabled")
        return s.monitor.check_once()

    @router.delete("/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_watch(watch_id: int, t: AvailabilityStore = Depends(tracker)) -> None:
        if not t.remove_watch(watch_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such watch")


def _item_routes(router: APIRouter, tracker: Callable, svc: Callable, settings: Settings) -> None:
    @router.get("/tracking/status", response_model=TrackingStatus)
    def tracking_status(t: AvailabilityStore = Depends(tracker)) -> TrackingStatus:
        stale_after = settings.tracking_stale_after_s
        return TrackingStatus(
            enabled=True,
            store=settings.tracking,
            stale_after_s=stale_after,
            watches=len(t.watches()),
            monitor_interval_s=settings.tracking_monitor_interval_s,
            enrich_cached=settings.tracking_enrich_cached,
            **t.summary(stale_after),
        )

    @router.get("/tracking/items", response_model=list[TrackedItem])
    def tracking_items(
        in_stock: bool | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        stale_after_s: float | None = None,
        limit: int = 100,
        t: AvailabilityStore = Depends(tracker),
    ) -> list[TrackedItem]:
        return t.items(
            in_stock=in_stock,
            price_min=price_min,
            price_max=price_max,
            stale_after_s=stale_after_s,
            limit=max(1, min(limit, 1000)),
        )

    @router.get("/tracking/items/{provider}/{product_id}", response_model=TrackedItem)
    def tracking_item(provider: str, product_id: str, t: AvailabilityStore = Depends(tracker)):
        item = t.item(provider, product_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not tracked")
        return item

    @router.post("/tracking/items/bulk", response_model=BulkLookupResponse)
    def tracking_bulk(body: BulkLookup, t: AvailabilityStore = Depends(tracker)):
        out = BulkLookupResponse()
        for ref in body.items:
            item = t.item(ref.provider, ref.product_id)
            (
                out.found.append(item)
                if item
                else out.missing.append(f"{ref.provider}/{ref.product_id}")
            )
        for url in body.urls:
            item = t.item_by_url(url)
            (out.found.append(item) if item else out.missing.append(url))
        return out

    @router.post("/tracking/refresh", response_model=RefreshSummary)
    def tracking_refresh(
        stale_after_s: float | None = Query(None, ge=0),
        limit: int | None = Query(None, ge=1, le=1000),
        s: Services = Depends(svc),
    ) -> RefreshSummary:
        if s.monitor is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "tracking is disabled")
        return s.monitor.refresh(stale_after_s=stale_after_s, limit=limit)
