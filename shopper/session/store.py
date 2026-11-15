"""Session store protocol with in-memory and SQLite implementations."""

from __future__ import annotations

import sqlite3
import threading
import time
from typing import Protocol

from shopper.contracts.context import SessionState


class SessionStore(Protocol):
    def get(self, conversation_id: str) -> SessionState: ...
    def put(self, state: SessionState) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._data: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def get(self, conversation_id: str) -> SessionState:
        with self._lock:
            state = self._data.get(conversation_id)
            return (
                state.model_copy(deep=True)
                if state
                else SessionState(conversation_id=conversation_id)
            )

    def put(self, state: SessionState) -> None:
        state.updated_at = time.time()
        with self._lock:
            self._data[state.conversation_id] = state.model_copy(deep=True)


class SQLiteSessionStore:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL, "
                "updated_at REAL NOT NULL)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, check_same_thread=False)

    def get(self, conversation_id: str) -> SessionState:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT state FROM sessions WHERE id = ?", (conversation_id,)
            ).fetchone()
        if not row:
            return SessionState(conversation_id=conversation_id)
        return SessionState.model_validate_json(row[0])

    def put(self, state: SessionState) -> None:
        state.updated_at = time.time()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO sessions (id, state, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET state = excluded.state, "
                "updated_at = excluded.updated_at",
                (state.conversation_id, state.model_dump_json(), state.updated_at),
            )
