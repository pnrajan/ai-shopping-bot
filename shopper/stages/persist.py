"""Stage 8: record the turn and the products shown so the next turn can refine."""

from __future__ import annotations

from shopper.contracts.context import RequestContext
from shopper.session.store import SessionStore

MAX_TURNS = 20


class PersistStage:
    name = "persist"

    def __init__(self, store: SessionStore):
        self._store = store

    def run(self, ctx: RequestContext) -> RequestContext:
        s = ctx.session
        s.turns.append({"role": "user", "content": ctx.request.recent_turn})
        if ctx.reply:
            s.turns.append({"role": "assistant", "content": ctx.reply})
        s.turns = s.turns[-MAX_TURNS:]
        if ctx.products:
            s.last_products = ctx.products
        self._store.put(s)
        return ctx
