"""Ordered stages with one run loop. Stages short-circuit by setting ``ctx.done``;
persistence always runs."""

from __future__ import annotations

import time

from shopper.contracts.chat import ChatRequest, ChatResponse
from shopper.contracts.context import LLMBudget, RequestContext, StageEvent
from shopper.logging import get_logger, log_event
from shopper.session.store import SessionStore
from shopper.stages.base import Stage

log = get_logger("pipeline")


class ShoppingPipeline:
    def __init__(self, stages: list[Stage], final: Stage, store: SessionStore, max_llm_calls: int):
        self._stages = stages
        self._final = final
        self._store = store
        self._max_llm = max_llm_calls

    def run(self, request: ChatRequest) -> ChatResponse:
        ctx = RequestContext(
            request=request,
            session=self._store.get(request.conversation_id),
            budget=LLMBudget(max_calls=self._max_llm),
        )
        for stage in self._stages:
            if ctx.done:
                break
            ctx = self._timed(stage, ctx)
        ctx = self._timed(self._final, ctx)
        if ctx.response is None:
            ctx.response = ChatResponse(
                response="Something went wrong assembling a reply.",
                conversation_id=request.conversation_id,
                success=False,
            )
        ctx.response.metadata.update(
            {
                "processing_time_ms": ctx.elapsed_ms(),
                "llm_calls": ctx.budget.used,
                "from_cache": bool(ctx.extras.get("from_cache")),
                "stages": [e.model_dump() for e in ctx.trace],
                "plan": [s.tool for s in ctx.plan.steps] if ctx.plan else [],
            }
        )
        log_event(
            log,
            "pipeline.done",
            conversation_id=request.conversation_id,
            ms=ctx.elapsed_ms(),
            llm_calls=ctx.budget.used,
            products=len(ctx.products),
        )
        return ctx.response

    @staticmethod
    def _timed(stage: Stage, ctx: RequestContext) -> RequestContext:
        started = time.perf_counter()
        ctx = stage.run(ctx)
        ctx.trace.append(
            StageEvent(stage=stage.name, ms=int((time.perf_counter() - started) * 1000))
        )
        return ctx
