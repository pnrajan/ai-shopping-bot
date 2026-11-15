"""Stage 5: run plan steps in order. A failed required step stops the plan."""

from __future__ import annotations

import time

from shopper.contracts.context import RequestContext
from shopper.contracts.plan import ExecutionResponse, StepResult
from shopper.contracts.product import Product
from shopper.contracts.tools import ToolInput
from shopper.llm.client import LLMClient
from shopper.search.handler import SearchHandler
from shopper.tools.registry import ToolDeps, ToolRegistry


class ExecuteStage:
    name = "execute"

    def __init__(self, registry: ToolRegistry, search: SearchHandler, llm: LLMClient):
        self._registry = registry
        self._search = search
        self._llm = llm

    def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.plan is None or ctx.understanding is None or not ctx.plan.steps:
            return ctx
        deps = ToolDeps(search=self._search, llm=self._llm, budget=ctx.budget)
        results: list[StepResult] = []
        for step in ctx.plan.steps:
            result = self._run_step(step.tool, step.inputs, ctx, deps)
            results.append(result)
            if not result.success and step.required:
                break
        ok = all(r.success for r, s in zip(results, ctx.plan.steps, strict=False) if s.required)
        ctx.execution = ExecutionResponse(success=ok, results=results)
        search_result = ctx.execution.result_for("product_search")
        if search_result and isinstance(search_result.data, list):
            ctx.products = [Product.model_validate(p) for p in search_result.data]
        return ctx

    def _run_step(self, tool: str, inputs: dict, ctx: RequestContext, deps: ToolDeps) -> StepResult:
        spec = self._registry.get(tool)
        if spec is None:
            return StepResult(tool=tool, success=False, error=f"unknown tool {tool!r}")
        assert ctx.understanding is not None
        started = time.perf_counter()
        out = spec.fn(
            ToolInput(understanding=ctx.understanding, turns=ctx.request.history, params=inputs),
            deps,
        )
        ms = int((time.perf_counter() - started) * 1000)
        if out.metadata.get("from_cache"):
            ctx.extras["from_cache"] = True
        return StepResult(
            tool=tool, success=out.success, data=out.data, error=out.error, latency_ms=ms
        )
