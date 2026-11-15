"""Stage 1: one structured LLM call that fills QueryUnderstanding."""

from __future__ import annotations

from ai_shopping_bot.contracts.context import RequestContext
from ai_shopping_bot.contracts.understanding import QueryUnderstanding
from ai_shopping_bot.llm import prompts
from ai_shopping_bot.llm.client import LLMClient
from ai_shopping_bot.settings import ModelRole
from ai_shopping_bot.stages.base import finish_with_clarification, history_text

MAX_CLARIFICATIONS = 1


class UnderstandStage:
    name = "understand"

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def run(self, ctx: RequestContext) -> RequestContext:
        user = (
            f"History:\n{history_text(ctx)}\n\n"
            f"Previously shown products: {len(ctx.session.last_products)}\n\n"
            f"Current turn: {ctx.request.recent_turn}"
        )
        qu = self._llm.complete(
            role=ModelRole.UNDERSTANDING,
            system=prompts.UNDERSTANDING_SYSTEM,
            user=user,
            budget=ctx.budget,
            purpose="understand",
            schema=QueryUnderstanding,
            max_tokens=700,
        )
        assert isinstance(qu, QueryUnderstanding)
        if not qu.search_queries:
            qu.search_queries = [qu.canonical_query or qu.query]
        ctx.understanding = qu
        ask = qu.should_ask_followup or qu.specialized.gift_shopping.needs_clarification
        if ask and ctx.session.clarifications_asked < MAX_CLARIFICATIONS:
            questions = qu.followup_questions or _gift_questions(qu)
            return finish_with_clarification(ctx, questions)
        return ctx


def _gift_questions(qu: QueryUnderstanding) -> list[str]:
    who = qu.specialized.gift_shopping.recipient or "them"
    return [f"What does your {who} like or enjoy?", f"Any hobbies or interests your {who} has?"]
