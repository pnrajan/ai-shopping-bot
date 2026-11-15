"""Re-check watched products against their provider on an interval.

Providers expose search, not get-by-id, so a check re-runs the search that first surfaced the
product (or the watch's own query or title) and keeps the result whose id matches. A watch with
no query, no title, and no prior sighting cannot be checked.
"""

from __future__ import annotations

import threading

from ai_shopping_bot.contracts.tracking import Alert, Observation, Watch
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
    ):
        self._store = store
        self._providers = providers
        self._interval = interval_s
        self._timeout = timeout_s
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

    def _lookup(self, watch: Watch) -> Observation | None:
        provider = self._providers.get(watch.provider)
        if provider is None:
            return None
        last = self._store.latest(watch.provider, watch.product_id)
        query = (
            watch.query
            or (last.query if last else "")
            or watch.title
            or (last.title if last else "")
        )
        if not query:
            return None
        try:
            results = provider.search(query, limit=20, timeout_s=self._timeout)
        except Exception as e:  # noqa: BLE001 - provider errors must not kill the loop
            log_event(log, "monitor.error", provider=watch.provider, error=str(e))
            return None
        for p in results.products:
            if p.id == watch.product_id:
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
            except Exception:  # keep the thread alive
                log.exception("monitor.loop")
