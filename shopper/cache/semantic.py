"""TTL cache keyed on a normalized query. In-memory by default, Redis under the ``redis`` extra.

"Semantic" here means normalization (case, whitespace, token order, stop words), not embeddings.
An embedding-similarity backend can implement the same ``get``/``put`` later and be measured.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "the", "for", "with", "and", "or", "of", "to", "in", "on", "best", "good"}


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...
    def put(self, key: str, value: Any, ttl_s: int) -> None: ...


class InMemoryBackend:
    def __init__(self, max_size: int = 1000):
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < time.time():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def put(self, key: str, value: Any, ttl_s: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl_s, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


class RedisBackend:
    def __init__(self, url: str, prefix: str = "shopper:search:"):
        import redis  # optional extra

        self._r = redis.Redis.from_url(url)
        self._prefix = prefix

    def get(self, key: str) -> Any | None:
        raw = self._r.get(self._prefix + key)
        return json.loads(raw) if raw else None

    def put(self, key: str, value: Any, ttl_s: int) -> None:
        self._r.set(self._prefix + key, json.dumps(value), ex=ttl_s)


class SemanticCache:
    def __init__(self, backend: CacheBackend | None = None, ttl_s: int = 24 * 3600):
        self._backend = backend or InMemoryBackend()
        self._ttl = ttl_s
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(queries: list[str], category: str | None = None) -> str:
        norm = sorted(
            " ".join(sorted(t for t in _TOKEN.findall(q.lower()) if t not in _STOP))
            for q in queries
        )
        return "|".join(norm) + ("#" + category.lower() if category else "")

    def get(self, key: str) -> Any | None:
        value = self._backend.get(key)
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def put(self, key: str, value: Any) -> None:
        self._backend.put(key, value, self._ttl)
