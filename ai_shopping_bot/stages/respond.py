"""Stage 6: turn products into a reply. One LLM call when products exist, templates otherwise."""

from __future__ import annotations

from ai_shopping_bot.contracts.context import RequestContext
from ai_shopping_bot.llm import prompts
from ai_shopping_bot.llm.client import LLMClient, LLMError
from ai_shopping_bot.settings import ModelRole
from ai_shopping_bot.stages.base import finish_with_products


class RespondStage:
    name = "respond"

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.response is not None:
            return ctx
        if not ctx.products:
            return finish_with_products(ctx, _no_results(ctx), note="no-results")
        text = self._compose(ctx)
        return finish_with_products(ctx, text)

    def _compose(self, ctx: RequestContext) -> str:
        if ctx.budget.remaining <= 0:
            return _template(ctx)
        try:
            text = self._llm.complete(
                role=ModelRole.RESPONSE,
                system=prompts.RESPONSE_SYSTEM,
                user=(
                    f"User asked: {ctx.request.recent_turn}\n\nProducts:\n"
                    f"{prompts.products_block([p.model_dump() for p in ctx.products[:6]])}"
                ),
                budget=ctx.budget,
                purpose="respond",
                max_tokens=350,
            )
        except LLMError:
            return _template(ctx)
        return str(text).strip() or _template(ctx)


def _template(ctx: RequestContext) -> str:
    top = ctx.products[:3]
    names = ", ".join(
        f"{p.title} (${p.price:.2f})" if p.price is not None else p.title for p in top
    )
    return f"I found {len(ctx.products)} options. Top picks: {names}."


def _no_results(ctx: RequestContext) -> str:
    if ctx.execution and ctx.execution.error:
        return "I could not reach the product catalog just now. Please try again in a moment."
    return (
        "I could not find products matching that. Try a different name, "
        "a broader category, or a higher budget."
    )
