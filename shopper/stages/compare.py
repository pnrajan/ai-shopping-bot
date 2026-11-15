"""Stage 3: for "X vs Y", search each product by name and keep the best match of each."""

from __future__ import annotations

from shopper.contracts.context import RequestContext
from shopper.contracts.product import Product
from shopper.search.handler import SearchHandler


class CompareStage:
    name = "compare"

    def __init__(self, search: SearchHandler):
        self._search = search

    def run(self, ctx: RequestContext) -> RequestContext:
        qu = ctx.understanding
        if qu is None or qu.intent != "comparison" or len(qu.search_queries) < 2:
            return ctx
        picked: list[Product] = []
        for name in qu.search_queries[:3]:
            single = qu.model_copy(update={"search_queries": [name], "canonical_query": name})
            found, _ = self._search.search(single, limit=3)
            if found:
                picked.append(found[0])
        if len(picked) < 2:
            return ctx
        ctx.products = picked
        ctx.extras["comparison"] = True
        return ctx
