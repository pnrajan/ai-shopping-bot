"""Shopping tools. Importing this package registers all three."""

from ai_shopping_bot.tools import product_search, research_product, review_summarizer  # noqa: F401
from ai_shopping_bot.tools.registry import ToolRegistry, get_registry, tool

__all__ = ["ToolRegistry", "get_registry", "tool"]
