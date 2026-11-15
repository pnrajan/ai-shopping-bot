"""Availability store: every product sighting becomes an observation; watches drive re-checks.

Alerts are derived by comparing each new observation with the previous one for the same
``(provider, product_id)``. Nothing here calls a provider; see ``monitor.py`` for that.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections import defaultdict
from typing import Protocol

from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.contracts.tracking import (
    Alert,
    AlertKind,
    Observation,
    PriceStats,
    TrackedItem,
    Watch,
    WatchCreate,
)
from ai_shopping_bot.tracking.urls import normalize_url

Key = tuple[str, str]

# Ignore price moves smaller than this fraction, so provider rounding does not spam alerts.
MIN_PRICE_MOVE = 0.01


class AvailabilityStore(Protocol):
    def record(self, products: list[Product], *, query: str = "") -> list[Alert]: ...
    def record_observation(self, obs: Observation) -> list[Alert]: ...
    def history(self, provider: str, product_id: str, limit: int = 100) -> list[Observation]: ...
    def latest(self, provider: str, product_id: str) -> Observation | None: ...
    def stats(self, provider: str, product_id: str) -> PriceStats: ...
    def add_watch(self, watch: WatchCreate) -> Watch: ...
    def remove_watch(self, watch_id: int) -> bool: ...
    def watches(self) -> list[Watch]: ...
    def alerts(self, limit: int = 50) -> list[Alert]: ...
    def item(self, provider: str, product_id: str) -> TrackedItem | None: ...
    def item_by_url(self, url: str) -> TrackedItem | None: ...
    def items(
        self,
        *,
        in_stock: bool | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        stale_after_s: float | None = None,
        limit: int = 100,
    ) -> list[TrackedItem]: ...
    def count_items(self) -> int: ...


def observation_from(product: Product, query: str = "") -> Observation | None:
    if not product.provider or not product.id:
        return None
    return Observation(
        query=query,
        provider=product.provider,
        product_id=product.id,
        title=product.title,
        url=product.url,
        price=product.price,
        currency=product.currency,
        in_stock=product.in_stock,
    )


def diff(prev: Observation | None, cur: Observation, watch: Watch | None) -> list[Alert]:
    """Alerts implied by ``cur`` following ``prev``. Target alerts need a watch."""
    out: list[Alert] = []
    base = {
        "provider": cur.provider,
        "product_id": cur.product_id,
        "title": cur.title or (prev.title if prev else ""),
        "previous": prev,
        "current": cur,
        "watch_id": watch.id if watch else None,
    }
    if prev is not None:
        if prev.price is not None and cur.price is not None and prev.price > 0:
            move = (cur.price - prev.price) / prev.price
            if move <= -MIN_PRICE_MOVE:
                out.append(Alert(kind=AlertKind.PRICE_DROP, **base))
            elif move >= MIN_PRICE_MOVE:
                out.append(Alert(kind=AlertKind.PRICE_RISE, **base))
        if prev.in_stock is False and cur.in_stock is True:
            out.append(Alert(kind=AlertKind.BACK_IN_STOCK, **base))
        elif prev.in_stock is True and cur.in_stock is False:
            out.append(Alert(kind=AlertKind.OUT_OF_STOCK, **base))
    if (
        watch is not None
        and watch.target_price is not None
        and cur.price is not None
        and cur.price <= watch.target_price
        and (prev is None or prev.price is None or prev.price > watch.target_price)
    ):
        out.append(Alert(kind=AlertKind.TARGET_REACHED, **base))
    return out


def compute_stats(provider: str, product_id: str, obs: list[Observation]) -> PriceStats:
    prices = [o.price for o in obs if o.price is not None]
    stock = [o.in_stock for o in obs if o.in_stock is not None]
    last = obs[-1] if obs else None
    return PriceStats(
        provider=provider,
        product_id=product_id,
        title=last.title if last else "",
        observations=len(obs),
        current_price=last.price if last else None,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        avg_price=round(sum(prices) / len(prices), 2) if prices else None,
        in_stock=last.in_stock if last else None,
        availability_ratio=round(sum(1 for s in stock if s) / len(stock), 3) if stock else None,
        first_seen=obs[0].observed_at if obs else None,
        last_seen=last.observed_at if last else None,
    )


def fold(prev: TrackedItem | None, obs: Observation) -> TrackedItem:
    """Current-state row after ``obs``. Keeps the last non-empty title, url, and query."""
    return TrackedItem(
        provider=obs.provider,
        product_id=obs.product_id,
        title=obs.title or (prev.title if prev else ""),
        url=obs.url or (prev.url if prev else ""),
        price=obs.price,
        currency=obs.currency,
        in_stock=obs.in_stock,
        query=obs.query or (prev.query if prev else ""),
        observations=(prev.observations if prev else 0) + 1,
        first_seen=prev.first_seen if prev else obs.observed_at,
        updated_at=obs.observed_at,
    )


def _matches(
    it: TrackedItem,
    in_stock: bool | None,
    price_min: float | None,
    price_max: float | None,
    stale_after_s: float | None,
    now: float,
) -> bool:
    if in_stock is not None and it.in_stock is not in_stock:
        return False
    if price_min is not None and (it.price is None or it.price < price_min):
        return False
    if price_max is not None and (it.price is None or it.price > price_max):
        return False
    return not (stale_after_s is not None and not it.is_stale(stale_after_s, now))


class _Base:
    """Shared record/diff logic; subclasses supply storage primitives."""

    def record(self, products: list[Product], *, query: str = "") -> list[Alert]:
        alerts: list[Alert] = []
        for p in products:
            obs = observation_from(p, query)
            if obs is not None:
                alerts.extend(self.record_observation(obs))
        return alerts

    def record_observation(self, obs: Observation) -> list[Alert]:
        prev = self.latest(obs.provider, obs.product_id)
        watch = self._watch_for(obs.provider, obs.product_id)
        alerts = diff(prev, obs, watch)
        self._append(obs, alerts)
        return alerts

    # storage primitives
    def latest(self, provider: str, product_id: str) -> Observation | None:
        raise NotImplementedError

    def _watch_for(self, provider: str, product_id: str) -> Watch | None:
        raise NotImplementedError

    def _append(self, obs: Observation, alerts: list[Alert]) -> None:
        raise NotImplementedError


class InMemoryAvailabilityStore(_Base):
    def __init__(self, max_history: int = 1000, max_alerts: int = 500):
        self._obs: dict[Key, list[Observation]] = defaultdict(list)
        self._items: dict[Key, TrackedItem] = {}
        self._by_url: dict[str, Key] = {}
        self._watches: dict[int, Watch] = {}
        self._alerts: list[Alert] = []
        self._next = 1
        self._max_history = max_history
        self._max_alerts = max_alerts
        self._lock = threading.Lock()

    def latest(self, provider: str, product_id: str) -> Observation | None:
        with self._lock:
            lst = self._obs.get((provider, product_id))
            return lst[-1] if lst else None

    def _watch_for(self, provider: str, product_id: str) -> Watch | None:
        with self._lock:
            for w in self._watches.values():
                if w.provider == provider and w.product_id == product_id:
                    return w
        return None

    def _append(self, obs: Observation, alerts: list[Alert]) -> None:
        key = (obs.provider, obs.product_id)
        with self._lock:
            lst = self._obs[key]
            lst.append(obs)
            del lst[: -self._max_history]
            item = fold(self._items.get(key), obs)
            self._items[key] = item
            if item.url:
                self._by_url[normalize_url(item.url)] = key
            self._alerts.extend(alerts)
            del self._alerts[: -self._max_alerts]

    def item(self, provider: str, product_id: str) -> TrackedItem | None:
        with self._lock:
            return self._items.get((provider, product_id))

    def item_by_url(self, url: str) -> TrackedItem | None:
        with self._lock:
            key = self._by_url.get(normalize_url(url))
            return self._items.get(key) if key else None

    def items(
        self,
        *,
        in_stock: bool | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        stale_after_s: float | None = None,
        limit: int = 100,
    ) -> list[TrackedItem]:
        now = time.time()
        with self._lock:
            rows = sorted(self._items.values(), key=lambda i: i.updated_at)
        out = [i for i in rows if _matches(i, in_stock, price_min, price_max, stale_after_s, now)]
        return out[:limit]

    def count_items(self) -> int:
        with self._lock:
            return len(self._items)

    def history(self, provider: str, product_id: str, limit: int = 100) -> list[Observation]:
        with self._lock:
            return list(self._obs.get((provider, product_id), []))[-limit:]

    def stats(self, provider: str, product_id: str) -> PriceStats:
        return compute_stats(provider, product_id, self.history(provider, product_id, 10_000))

    def add_watch(self, watch: WatchCreate) -> Watch:
        with self._lock:
            for w in self._watches.values():
                if w.provider == watch.provider and w.product_id == watch.product_id:
                    w.target_price = watch.target_price
                    w.title = watch.title or w.title
                    w.query = watch.query or w.query
                    return w
            w = Watch(id=self._next, **watch.model_dump())
            self._watches[w.id] = w
            self._next += 1
            return w

    def remove_watch(self, watch_id: int) -> bool:
        with self._lock:
            return self._watches.pop(watch_id, None) is not None

    def watches(self) -> list[Watch]:
        with self._lock:
            return list(self._watches.values())

    def alerts(self, limit: int = 50) -> list[Alert]:
        with self._lock:
            return list(reversed(self._alerts[-limit:]))


class SQLiteAvailabilityStore(_Base):
    """Three tables in the same file as the SQLite session store, if you point it there."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL, product_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
                    price REAL, currency TEXT NOT NULL DEFAULT 'USD',
                    in_stock INTEGER, query TEXT NOT NULL DEFAULT '', observed_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS obs_key ON observations (provider, product_id, id);
                CREATE TABLE IF NOT EXISTS watches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL, product_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '', query TEXT NOT NULL DEFAULT '',
                    target_price REAL, created_at REAL NOT NULL,
                    UNIQUE (provider, product_id));
                CREATE TABLE IF NOT EXISTS items (
                    provider TEXT NOT NULL, product_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
                    url_norm TEXT NOT NULL DEFAULT '',
                    price REAL, currency TEXT NOT NULL DEFAULT 'USD', in_stock INTEGER,
                    query TEXT NOT NULL DEFAULT '', observations INTEGER NOT NULL DEFAULT 0,
                    first_seen REAL NOT NULL, updated_at REAL NOT NULL,
                    PRIMARY KEY (provider, product_id));
                CREATE INDEX IF NOT EXISTS items_url ON items (url_norm);
                CREATE INDEX IF NOT EXISTS items_updated ON items (updated_at);
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL, payload TEXT NOT NULL);
                """
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, check_same_thread=False)

    @staticmethod
    def _row_obs(r: tuple) -> Observation:
        return Observation(
            provider=r[0],
            product_id=r[1],
            title=r[2],
            url=r[3],
            price=r[4],
            currency=r[5],
            in_stock=None if r[6] is None else bool(r[6]),
            query=r[7],
            observed_at=r[8],
        )

    _OBS_COLS = "provider, product_id, title, url, price, currency, in_stock, query, observed_at"
    _WATCH_COLS = "id, provider, product_id, title, query, target_price, created_at"
    _ITEM_COLS = (
        "provider, product_id, title, url, price, currency, in_stock, query, observations, "
        "first_seen, updated_at"
    )

    @staticmethod
    def _row_item(r: tuple) -> TrackedItem:
        return TrackedItem(
            provider=r[0],
            product_id=r[1],
            title=r[2],
            url=r[3],
            price=r[4],
            currency=r[5],
            in_stock=None if r[6] is None else bool(r[6]),
            query=r[7],
            observations=r[8],
            first_seen=r[9],
            updated_at=r[10],
        )

    def _item_in(self, c: sqlite3.Connection, provider: str, product_id: str) -> TrackedItem | None:
        r = c.execute(
            f"SELECT {self._ITEM_COLS} FROM items WHERE provider = ? AND product_id = ?",
            (provider, product_id),
        ).fetchone()
        return self._row_item(r) if r else None

    def item(self, provider: str, product_id: str) -> TrackedItem | None:
        with self._lock, self._conn() as c:
            return self._item_in(c, provider, product_id)

    def item_by_url(self, url: str) -> TrackedItem | None:
        with self._lock, self._conn() as c:
            r = c.execute(
                f"SELECT {self._ITEM_COLS} FROM items WHERE url_norm = ? ORDER BY updated_at DESC "
                "LIMIT 1",
                (normalize_url(url),),
            ).fetchone()
        return self._row_item(r) if r else None

    def items(
        self,
        *,
        in_stock: bool | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        stale_after_s: float | None = None,
        limit: int = 100,
    ) -> list[TrackedItem]:
        clauses, args = [], []
        if in_stock is not None:
            clauses.append("in_stock = ?")
            args.append(int(in_stock))
        if price_min is not None:
            clauses.append("price >= ?")
            args.append(price_min)
        if price_max is not None:
            clauses.append("price <= ?")
            args.append(price_max)
        if stale_after_s is not None:
            clauses.append("updated_at < ?")
            args.append(time.time() - stale_after_s)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT {self._ITEM_COLS} FROM items {where} ORDER BY updated_at LIMIT ?",
                (*args, limit),
            ).fetchall()
        return [self._row_item(r) for r in rows]

    def count_items(self) -> int:
        with self._lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def latest(self, provider: str, product_id: str) -> Observation | None:
        with self._lock, self._conn() as c:
            r = c.execute(
                f"SELECT {self._OBS_COLS} FROM observations WHERE provider = ? AND product_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (provider, product_id),
            ).fetchone()
        return self._row_obs(r) if r else None

    def _watch_for(self, provider: str, product_id: str) -> Watch | None:
        with self._lock, self._conn() as c:
            r = c.execute(
                f"SELECT {self._WATCH_COLS} FROM watches WHERE provider = ? AND product_id = ?",
                (provider, product_id),
            ).fetchone()
        return self._row_watch(r) if r else None

    @staticmethod
    def _row_watch(r: tuple) -> Watch:
        return Watch(
            id=r[0],
            provider=r[1],
            product_id=r[2],
            title=r[3],
            query=r[4],
            target_price=r[5],
            created_at=r[6],
        )

    def _append(self, obs: Observation, alerts: list[Alert]) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                f"INSERT INTO observations ({self._OBS_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    obs.provider,
                    obs.product_id,
                    obs.title,
                    obs.url,
                    obs.price,
                    obs.currency,
                    None if obs.in_stock is None else int(obs.in_stock),
                    obs.query,
                    obs.observed_at,
                ),
            )
            item = fold(self._item_in(c, obs.provider, obs.product_id), obs)
            c.execute(
                f"INSERT INTO items ({self._ITEM_COLS}, url_norm) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(provider, product_id) DO UPDATE SET title = excluded.title, "
                "url = excluded.url, url_norm = excluded.url_norm, price = excluded.price, "
                "currency = excluded.currency, in_stock = excluded.in_stock, "
                "query = excluded.query, observations = excluded.observations, "
                "updated_at = excluded.updated_at",
                (
                    item.provider,
                    item.product_id,
                    item.title,
                    item.url,
                    item.price,
                    item.currency,
                    None if item.in_stock is None else int(item.in_stock),
                    item.query,
                    item.observations,
                    item.first_seen,
                    item.updated_at,
                    normalize_url(item.url) if item.url else "",
                ),
            )
            c.executemany(
                "INSERT INTO alerts (created_at, payload) VALUES (?, ?)",
                [(time.time(), a.model_dump_json()) for a in alerts],
            )

    def history(self, provider: str, product_id: str, limit: int = 100) -> list[Observation]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT {self._OBS_COLS} FROM observations WHERE provider = ? AND product_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (provider, product_id, limit),
            ).fetchall()
        return [self._row_obs(r) for r in reversed(rows)]

    def stats(self, provider: str, product_id: str) -> PriceStats:
        return compute_stats(provider, product_id, self.history(provider, product_id, 10_000))

    def add_watch(self, watch: WatchCreate) -> Watch:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO watches "
                "(provider, product_id, title, query, target_price, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(provider, product_id) DO UPDATE SET "
                "target_price = excluded.target_price, "
                "title = CASE WHEN excluded.title = '' THEN watches.title ELSE excluded.title END, "
                "query = CASE WHEN excluded.query = '' THEN watches.query ELSE excluded.query END",
                (
                    watch.provider,
                    watch.product_id,
                    watch.title,
                    watch.query,
                    watch.target_price,
                    time.time(),
                ),
            )
            r = c.execute(
                f"SELECT {self._WATCH_COLS} FROM watches WHERE provider = ? AND product_id = ?",
                (watch.provider, watch.product_id),
            ).fetchone()
        return self._row_watch(r)

    def remove_watch(self, watch_id: int) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM watches WHERE id = ?", (watch_id,)).rowcount > 0

    def watches(self) -> list[Watch]:
        with self._lock, self._conn() as c:
            rows = c.execute(f"SELECT {self._WATCH_COLS} FROM watches ORDER BY id").fetchall()
        return [self._row_watch(r) for r in rows]

    def alerts(self, limit: int = 50) -> list[Alert]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT payload FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Alert.model_validate_json(r[0]) for r in rows]
