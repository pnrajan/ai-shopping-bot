"""Price history, watches, and alerts. Mounted only when a tracker is configured."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status

from ai_shopping_bot.api.wiring import Services
from ai_shopping_bot.contracts.tracking import Alert, ProductHistory, Watch, WatchCreate
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
        limit: int | None = None,
        t: AvailabilityStore = Depends(tracker),
    ) -> ProductHistory:
        n = max(1, min(limit or settings.tracking_history_limit, 1000))
        history = t.history(provider, product_id, n)
        if not history:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no observations for this product")
        alerts = [a for a in t.alerts(200) if a.provider == provider and a.product_id == product_id]
        return ProductHistory(stats=t.stats(provider, product_id), history=history, alerts=alerts)

    _watch_routes(router, tracker, svc)

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
