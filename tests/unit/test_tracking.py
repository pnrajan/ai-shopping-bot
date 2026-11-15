from __future__ import annotations

import pytest

from ai_shopping_bot.contracts.product import Product, ProviderResults
from ai_shopping_bot.contracts.tracking import AlertKind, Observation, WatchCreate
from ai_shopping_bot.providers.fake import FakeProvider
from ai_shopping_bot.tracking import (
    AvailabilityMonitor,
    InMemoryAvailabilityStore,
    SQLiteAvailabilityStore,
)


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryAvailabilityStore()
    return SQLiteAvailabilityStore(str(tmp_path / "t.db"))


def obs(price, in_stock=True, **kw) -> Observation:
    return Observation(
        provider="fake", product_id="p1", title="Widget", price=price, in_stock=in_stock, **kw
    )


def test_record_builds_history_and_stats(store):
    assert store.record_observation(obs(100)) == []
    store.record_observation(obs(80))
    store.record_observation(obs(120, in_stock=False))
    hist = store.history("fake", "p1")
    assert [o.price for o in hist] == [100, 80, 120]
    st = store.stats("fake", "p1")
    assert (st.min_price, st.max_price, st.current_price, st.avg_price) == (80, 120, 120, 100)
    assert st.in_stock is False
    assert st.availability_ratio == pytest.approx(2 / 3, abs=1e-3)
    assert st.observations == 3


def test_alerts_on_price_and_stock_changes(store):
    store.record_observation(obs(100))
    kinds = [a.kind for a in store.record_observation(obs(90, in_stock=False))]
    assert kinds == [AlertKind.PRICE_DROP, AlertKind.OUT_OF_STOCK]
    kinds = [a.kind for a in store.record_observation(obs(95, in_stock=True))]
    assert kinds == [AlertKind.PRICE_RISE, AlertKind.BACK_IN_STOCK]
    # sub-1% moves are noise
    assert store.record_observation(obs(95.5)) == []
    assert len(store.alerts()) == 4
    assert store.alerts(1)[0].kind == AlertKind.BACK_IN_STOCK


def test_watch_target_price_fires_once(store):
    w = store.add_watch(WatchCreate(provider="fake", product_id="p1", target_price=50))
    assert w.id >= 1
    store.record_observation(obs(60))
    kinds = [a.kind for a in store.record_observation(obs(49))]
    assert AlertKind.TARGET_REACHED in kinds
    assert all(a.watch_id == w.id for a in store.alerts() if a.kind == AlertKind.TARGET_REACHED)
    # still below target, no repeat
    assert AlertKind.TARGET_REACHED not in [a.kind for a in store.record_observation(obs(48.5))]


def test_watch_upsert_and_remove(store):
    a = store.add_watch(
        WatchCreate(provider="fake", product_id="p1", title="Widget", target_price=10)
    )
    b = store.add_watch(WatchCreate(provider="fake", product_id="p1", target_price=20))
    assert a.id == b.id and b.target_price == 20 and b.title == "Widget"
    assert len(store.watches()) == 1
    assert store.remove_watch(a.id) is True
    assert store.remove_watch(a.id) is False
    assert store.watches() == []


def test_record_products_skips_those_without_identity(store):
    products = [
        Product(id="x", provider="fake", title="A", price=1.0),
        Product(title="no id", price=2.0),
    ]
    store.record(products)
    assert store.history("fake", "x") and store.stats("fake", "x").current_price == 1.0


class DriftingProvider(FakeProvider):
    """Fake catalog whose prices fall 10% on every search."""

    def __init__(self) -> None:
        self.calls = 0

    def search(self, query, *, category=None, limit=10, timeout_s=8.0) -> ProviderResults:
        self.calls += 1
        res = super().search(query, category=category, limit=limit, timeout_s=timeout_s)
        for p in res.products:
            p.price = round(p.price * (0.9**self.calls), 2)
        return res


def test_monitor_rechecks_watches_and_emits_alerts():
    store = InMemoryAvailabilityStore()
    provider = DriftingProvider()
    first = provider.search("gaming laptop").products[0]
    store.record([first], query="gaming laptop")
    store.add_watch(WatchCreate(provider="fake", product_id=first.id))
    monitor = AvailabilityMonitor(store, {"fake": provider})
    alerts = monitor.check_once()
    assert [a.kind for a in alerts] == [AlertKind.PRICE_DROP]
    assert alerts[0].current.price < first.price
    assert len(store.history("fake", first.id)) == 2
    assert store.history("fake", first.id)[-1].query == "gaming laptop"


def test_monitor_skips_unknown_provider_and_blank_title():
    store = InMemoryAvailabilityStore()
    store.add_watch(WatchCreate(provider="nope", product_id="p"))
    store.add_watch(WatchCreate(provider="fake", product_id="never-seen"))
    assert AvailabilityMonitor(store, {"fake": FakeProvider()}).check_once() == []


def test_monitor_thread_start_stop_is_noop_when_disabled():
    m = AvailabilityMonitor(InMemoryAvailabilityStore(), {}, interval_s=0)
    m.start()
    m.stop()
