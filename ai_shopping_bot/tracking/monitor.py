"""Re-check watched products against their provider on an interval.

Providers expose search, not get-by-id, so a check re-runs the search that first surfaced the
product (or the watch's own query or title) and keeps the result whose id matches. A watch with
no query, no title, and no prior sighting cannot be checked.
"""

from __future__ import annotations

import threading
import time

from ai_shopping_bot.contracts.tracking import (
    Alert,
    Observation,
    RefreshSummary,
    Watch,
)
from ai_shopping_bot.logging import get_logger, log_event
from ai_shopping_bot.providers.base import CatalogProvider
from ai_shopping_bot.tracking.store import AvailabilityStore, observation_from

log = get_logger("tracking")


class AvailabilityMonitor:
    def __init__(
        self,
        store: AvailabilityStore,
        providers: dict[str, CatalogProvider],
        *,
        interval_s: float = 0,
        timeout_s: float = 8.0,
        stale_after_s: float = 6 * 3600,
        refresh_limit: int = 50,
    ):
        self._store = store
        self._providers = providers
        self._interval = interval_s
        self._timeout = timeout_s
        self._stale_after = stale_after_s
        self._refresh_limit = refresh_limit
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check_once(self) -> list[Alert]:
        alerts: list[Alert] = []
        for watch in self._store.watches():
            obs = self._lookup(watch)
            if obs is None:
                log_event(log, "monitor.miss", provider=watch.provider, product_id=watch.product_id)
                continue
            alerts.extend(self._store.record_observation(obs))
        log_event(log, "monitor.checked", watches=len(self._store.watches()), alerts=len(alerts))
        return alerts

    def refresh(
        self, *, stale_after_s: float | None = None, limit: int | None = None
    ) -> RefreshSummary:
        """Re-check every tracked item not seen for ``stale_after_s``, oldest first.

        This is the AvailabilityDB price-update job: it keeps the current-state table fresh
        for everything seen, not only for watched products.
        """
        started = time.perf_counter()
        stale_after = self._stale_after if stale_after_s is None else stale_after_s
        items = self._store.items(stale_after_s=stale_after, limit=limit or self._refresh_limit)
        out = RefreshSummary(candidates=len(items))
        for it in items:
            obs = self._search(it.provider, it.product_id, it.query or it.title)
            out.checked += 1
            if obs is None:
                out.missed += 1
                continue
            alerts = self._store.record_observation(obs)
            out.updated += 1
            if alerts:
                out.changed += 1
                out.alerts.extend(alerts)
        out.duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(log, "monitor.refreshed", **out.model_dump(exclude={"alerts"}))
        return out

    def _lookup(self, watch: Watch) -> Observation | None:
        last = self._store.latest(watch.provider, watch.product_id)
        query = (
            watch.query
            or (last.query if last else "")
            or watch.title
            or (last.title if last else "")
        )
        return self._search(watch.provider, watch.product_id, query)

    def _search(self, provider_name: str, product_id: str, query: str) -> Observation | None:
        provider = self._providers.get(provider_name)
        if provider is None or not query:
            return None
        try:
            results = provider.search(query, limit=20, timeout_s=self._timeout)
        except Exception as e:  # noqa: BLE001 - provider errors must not kill the loop
            log_event(log, "monitor.error", provider=provider_name, error=str(e))
            return None
        for p in results.products:
            if p.id == product_id:
                return observation_from(p, query)
        return None

    def start(self) -> None:
        if self._interval <= 0 or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="availability-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.check_once()
                self.refresh()
            except Exception:  # keep the thread alive
                log.exception("monitor.loop")
