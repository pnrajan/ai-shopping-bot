"""Stage 7: optional additions driven by specialized intents. Each is independently toggleable
and skipped silently when the LLM budget is exhausted."""

from __future__ import annotations

from shopper.contracts.context import RequestContext
from shopper.llm import prompts
from shopper.llm.client import LLMClient, LLMError
from shopper.settings import ModelRole, Settings


class EnrichStage:
    name = "enrich"

    def __init__(self, llm: LLMClient, settings: Settings):
        self._llm = llm
        self._s = settings

    def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.response is None or ctx.understanding is None or not ctx.products:
            return ctx
        sp = ctx.understanding.specialized
        additions: list[str] = []
        if self._s.enrich_comparison and ctx.extras.get("comparison") and len(ctx.products) >= 2:
            additions.append(
                self._call("compare", prompts.COMPARISON_SYSTEM, _compare_user(ctx), ctx)
            )
        if self._s.enrich_essentials and sp.essentials_checklist.detected:
            topic = sp.essentials_checklist.topic or ctx.understanding.canonical_query
            additions.append(
                self._call("essentials", prompts.ESSENTIALS_SYSTEM, f"Topic: {topic}", ctx)
            )
        if self._s.enrich_rationale and sp.product_rationale.detected:
            additions.append(
                self._call("rationale", prompts.RATIONALE_SYSTEM, _rationale_user(ctx), ctx)
            )
        extra = "\n\n".join(a for a in additions if a)
        if extra:
            ctx.response.response = f"{ctx.response.response}\n\n{extra}"
            ctx.reply = ctx.response.response
        return ctx

    def _call(self, purpose: str, system: str, user: str, ctx: RequestContext) -> str:
        if ctx.budget.remaining <= 0:
            return ""
        try:
            out = self._llm.complete(
                role=ModelRole.ENRICH,
                system=system,
                user=user,
                budget=ctx.budget,
                purpose=purpose,
                max_tokens=400,
            )
        except LLMError:
            return ""
        return str(out).strip()


def _compare_user(ctx: RequestContext) -> str:
    dims = [a.name for a in ctx.understanding.attributes] if ctx.understanding else []
    return (
        f"Dimensions: {', '.join(dims) or 'price, rating, key features'}\n\nProducts:\n"
        f"{prompts.products_block([p.model_dump() for p in ctx.products[:4]])}"
    )


def _rationale_user(ctx: RequestContext) -> str:
    assert ctx.understanding is not None
    crit = ctx.understanding.specialized.product_rationale.criteria or [
        a.name for a in ctx.understanding.attributes
    ]
    return (
        f"Criteria: {', '.join(crit) or 'the request'}\nUser asked: {ctx.request.recent_turn}\n\n"
        f"Products:\n{prompts.products_block([p.model_dump() for p in ctx.products[:5]])}"
    )
