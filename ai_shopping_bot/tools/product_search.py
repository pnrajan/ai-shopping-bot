"""product_search tool: thin wrapper over the search handler."""

from __future__ import annotations

from ai_shopping_bot.contracts.tools import ToolInput, ToolOutput
from ai_shopping_bot.tools.registry import ToolDeps, tool


@tool("product_search", "Find products matching the understood query and attributes")
def product_search(inp: ToolInput, deps: ToolDeps) -> ToolOutput:
    limit = int(inp.params.get("limit", 10))
    products, meta = deps.search.search(inp.understanding, limit=limit)
    if not products:
        return ToolOutput(success=False, error="no products found", metadata=meta)
    return ToolOutput(success=True, data=[p.model_dump() for p in products], metadata=meta)
