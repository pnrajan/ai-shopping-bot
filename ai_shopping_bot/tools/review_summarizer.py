"""review_summarizer tool: LLM summary of what buyers say about a product."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ai_shopping_bot.contracts.tools import ToolInput, ToolOutput
from ai_shopping_bot.llm import prompts
from ai_shopping_bot.llm.client import LLMError
from ai_shopping_bot.settings import ModelRole
from ai_shopping_bot.tools.registry import ToolDeps, tool


class ReviewSummary(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    sentiment: str = "mixed"
    confidence: float = 0.5


@tool("review_summarizer", "Summarize buyer reviews for a named product")
def review_summarizer(inp: ToolInput, deps: ToolDeps) -> ToolOutput:
    name = inp.params.get("product_name") or inp.understanding.canonical_query
    if not name:
        return ToolOutput(success=False, error="product_name required")
    try:
        result = deps.llm.complete(
            role=ModelRole.ENRICH,
            system=prompts.REVIEW_SYSTEM,
            user=f"Product: {name}",
            budget=deps.budget,
            purpose="review_summarizer",
            schema=ReviewSummary,
            max_tokens=400,
        )
    except LLMError as e:
        return ToolOutput(success=False, error=str(e))
    return ToolOutput(success=True, data={"product_name": name, **result.model_dump()})
