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


# ---- current-state items, URL lookup, enrichment (ported from AvailabilityDB) ----


def test_items_table_tracks_current_state_and_url(store):
    store.record_observation(obs(100, url="https://Shop.example.com/p/1/?utm_source=x&ref=abc"))
    store.record_observation(obs(90, in_stock=False))
    it = store.item("fake", "p1")
    assert it is not None
    assert (it.price, it.in_stock, it.observations) == (90, False, 2)
    assert it.url.startswith("https://Shop.example.com")  # last non-empty url kept
    assert store.item_by_url("https://shop.example.com/p/1?ref=zzz") == it
    assert store.item_by_url("https://shop.example.com/other") is None
    assert store.count_items() == 1


def test_items_filters(store):
    store.record_observation(Observation(provider="fake", product_id="a", price=10, in_stock=True))
    store.record_observation(Observation(provider="fake", product_id="b", price=50, in_stock=False))
    store.record_observation(Observation(provider="fake", product_id="c", price=90, in_stock=True))
    assert [i.product_id for i in store.items(in_stock=True)] == ["a", "c"]
    assert [i.product_id for i in store.items(price_min=20, price_max=60)] == ["b"]
    assert store.items(stale_after_s=3600) == []
    assert len(store.items(stale_after_s=0)) == 3
    assert len(store.items(limit=2)) == 2


def test_enrich_overlays_newer_tracked_state():
    from ai_shopping_bot.tracking.enrich import enrich

    store = InMemoryAvailabilityStore()
    cached_at = 1000.0
    store.record_observation(
        Observation(provider="fake", product_id="x", price=80, in_stock=False, observed_at=2000.0)
    )
    store.record_observation(
        Observation(provider="fake", product_id="old", price=1, in_stock=True, observed_at=500.0)
    )
    products = [
        Product(id="x", provider="fake", title="X", price=100, in_stock=True),
        Product(id="old", provider="fake", title="Old", price=5, in_stock=True),
        Product(id="never", provider="fake", title="N", price=7),
        Product(title="anon", price=3),
    ]
    res = enrich(products, store, newer_than=cached_at)
    assert (res.looked_up, res.hits, res.changed) == (3, 1, 1)
    assert res.products[0].price == 80 and res.products[0].in_stock is False
    assert res.products[1].price == 5  # older than the cache entry, left alone
    assert res.products[2].price == 7 and res.products[3].title == "anon"


def test_refresh_rechecks_stale_items_not_only_watches():
    store = InMemoryAvailabilityStore()
    provider = DriftingProvider()
    seen = provider.search("gaming laptop", limit=3).products
    store.record(seen, query="gaming laptop")
    monitor = AvailabilityMonitor(store, {"fake": provider})
    assert monitor.refresh().candidates == 0  # nothing stale yet
    summary = monitor.refresh(stale_after_s=0, limit=2)
    assert (summary.candidates, summary.checked, summary.updated, summary.missed) == (2, 2, 2, 0)
    assert summary.changed == 2 and all(a.kind == AlertKind.PRICE_DROP for a in summary.alerts)
    assert store.item("fake", seen[0].id).observations == 2


def test_normalize_url():
    from ai_shopping_bot.tracking.urls import normalize_url

    a = normalize_url("HTTPS://Example.com/p/1/?b=2&utm_campaign=x&a=1&ref=abc&tag=t#frag")
    assert a == "https://example.com/p/1?a=1&b=2"
    assert normalize_url("") == ""
    # exact-name matching: legitimate params that merely start with ref/tag survive
    assert "refurbished=1" in normalize_url("https://s/p?refurbished=1")
    assert "tags=blue" in normalize_url("https://s/p?tags=blue")


def test_fold_keeps_known_price_when_sighting_lacks_it(store):
    store.record_observation(obs(99))
    store.record_observation(
        Observation(provider="fake", product_id="p1", price=None, in_stock=None)
    )
    it = store.item("fake", "p1")
    assert (it.price, it.in_stock, it.observations) == (99, True, 2)


def test_items_for_batch_and_blank_url(store):
    store.record_observation(
        Observation(provider="fake", product_id="a", price=1, url="https://s/a")
    )
    store.record_observation(Observation(provider="fake", product_id="nourl", price=2))
    got = store.items_for([("fake", "a"), ("fake", "zz")])
    assert list(got) == [("fake", "a")]
    assert store.items_for([]) == {}
    assert store.item_by_url("") is None and store.item_by_url("   ") is None


def test_summary_matches_items(store):
    store.record_observation(Observation(provider="fake", product_id="a", price=10, in_stock=True))
    store.record_observation(Observation(provider="fake", product_id="b", price=30, in_stock=False))
    store.record_observation(Observation(provider="fake", product_id="c", price=None))
    s = store.summary(stale_after_s=3600)
    assert (s["items"], s["available"], s["unavailable"], s["unknown"], s["stale"]) == (
        3,
        1,
        1,
        1,
        0,
    )
    assert (s["min_price"], s["max_price"], s["avg_price"]) == (10, 30, 20)
    assert store.summary(stale_after_s=0)["stale"] == 3


def test_refresh_touches_misses_so_they_do_not_starve():
    store = InMemoryAvailabilityStore()
    store.record_observation(Observation(provider="ghost", product_id="g", price=1, query="x"))
    store.record_observation(Observation(provider="fake", product_id="f", price=1, query="y"))
    before = store.item("ghost", "g").updated_at
    monitor = AvailabilityMonitor(store, {"fake": FakeProvider()}, refresh_limit=1)
    out = monitor.refresh(stale_after_s=0, limit=1)
    assert out.missed == 1 and store.item("ghost", "g").updated_at > before
    # next pass picks the other item instead of the same miss
    assert store.items(stale_after_s=0, limit=1)[0].product_id == "f"
    assert monitor.refresh(stale_after_s=0, limit=5000).candidates <= 1
