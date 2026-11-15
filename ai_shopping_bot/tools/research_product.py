"""research_product tool: LLM buyer's brief for a named product."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ai_shopping_bot.contracts.tools import ToolInput, ToolOutput
from ai_shopping_bot.llm import prompts
from ai_shopping_bot.llm.client import LLMError
from ai_shopping_bot.settings import ModelRole
from ai_shopping_bot.tools.registry import ToolDeps, tool


class ResearchBrief(BaseModel):
    research: str
    key_features: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.5


@tool("research_product", "Research features, pros and cons of a named product")
def research_product(inp: ToolInput, deps: ToolDeps) -> ToolOutput:
    name = inp.params.get("product_name") or inp.understanding.canonical_query
    if not name:
        return ToolOutput(success=False, error="product_name required")
    try:
        result = deps.llm.complete(
            role=ModelRole.ENRICH,
            system=prompts.RESEARCH_SYSTEM,
            user=f"Product: {name}\nContext: {inp.params.get('context', '')}",
            budget=deps.budget,
            purpose="research_product",
            schema=ResearchBrief,
            max_tokens=500,
        )
    except LLMError as e:
        return ToolOutput(success=False, error=str(e))
    return ToolOutput(success=True, data={"product_name": name, **result.model_dump()})
