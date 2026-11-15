"""Stage protocol and shared helpers."""

from __future__ import annotations

from typing import Protocol

from shopper.contracts.chat import ChatResponse, DataType
from shopper.contracts.context import RequestContext


class Stage(Protocol):
    name: str

    def run(self, ctx: RequestContext) -> RequestContext: ...


def history_text(ctx: RequestContext, last_n: int = 6) -> str:
    turns = ctx.request.history[-last_n:]
    return "\n".join(f"{t.role.value}: {t.content}" for t in turns) or "(none)"


def finish_with_products(ctx: RequestContext, reply: str, note: str = "") -> RequestContext:
    ctx.reply = reply
    ctx.response = ChatResponse(
        response=reply,
        conversation_id=ctx.request.conversation_id,
        data=[p.model_dump() for p in ctx.products],
        data_type=DataType.PRODUCTS if ctx.products else DataType.GENERAL,
        data_count=len(ctx.products),
        metadata={"note": note} if note else {},
    )
    return ctx


def finish_with_clarification(ctx: RequestContext, questions: list[str]) -> RequestContext:
    lead = "I need a bit more information to find the right products."
    ctx.reply = lead + " " + " ".join(questions)
    ctx.session.clarifications_asked += 1
    ctx.response = ChatResponse(
        response=ctx.reply,
        conversation_id=ctx.request.conversation_id,
        data_type=DataType.CLARIFICATION,
        clarification_questions=questions,
    )
    ctx.done = True
    return ctx
