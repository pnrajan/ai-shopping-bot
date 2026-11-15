"""Stage 4: choose tool steps. Pattern table first, LLM planner only for unknown intents."""

from __future__ import annotations

from shopper.contracts.context import RequestContext
from shopper.contracts.plan import ExecutionPlan, ExecutionStep
from shopper.llm import prompts
from shopper.llm.client import LLMClient, LLMError
from shopper.settings import ModelRole

PATTERNS: dict[str, ExecutionPlan] = {
    "shopping": ExecutionPlan(
        route="product_search",
        steps=[ExecutionStep(tool="product_search", inputs={"limit": 10}, why="find products")],
    ),
    "browse": ExecutionPlan(
        route="product_search",
        steps=[ExecutionStep(tool="product_search", inputs={"limit": 15}, why="browse catalog")],
    ),
    "comparison": ExecutionPlan(
        route="product_comparison",
        steps=[ExecutionStep(tool="product_search", inputs={"limit": 5}, why="find candidates")],
    ),
}


class PlanStage:
    name = "plan"

    def __init__(self, llm: LLMClient | None = None):
        self._llm = llm

    def run(self, ctx: RequestContext) -> RequestContext:
        qu = ctx.understanding
        if qu is None:
            return ctx
        if ctx.products:
            ctx.plan = ExecutionPlan(route="prefilled", steps=[])
            return ctx
        plan = PATTERNS.get(qu.intent)
        if plan is None and self._llm and ctx.budget.remaining > 1:
            plan = self._llm_plan(ctx)
        ctx.plan = (plan or PATTERNS["shopping"]).model_copy(deep=True)
        return ctx

    def _llm_plan(self, ctx: RequestContext) -> ExecutionPlan | None:
        assert self._llm is not None and ctx.understanding is not None
        try:
            result = self._llm.complete(
                role=ModelRole.PLANNING,
                system=prompts.PLANNER_SYSTEM,
                user=ctx.understanding.model_dump_json(),
                budget=ctx.budget,
                purpose="plan",
                schema=ExecutionPlan,
                max_tokens=300,
            )
        except LLMError:
            return None
        if not isinstance(result, ExecutionPlan):
            return None
        result.source = "llm"
        return result
