from ai_shopping_bot.contracts.chat import ChatRequest
from ai_shopping_bot.contracts.context import LLMBudget, RequestContext, SessionState
from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.contracts.understanding import QueryUnderstanding
from ai_shopping_bot.llm.fake import FakeLLM
from ai_shopping_bot.stages.plan import PATTERNS, PlanStage
from ai_shopping_bot.stages.respond import RespondStage
from ai_shopping_bot.tools.registry import get_registry


def _ctx(turn="laptop under 1000", intent="shopping", products=None):
    ctx = RequestContext(
        request=ChatRequest(recent_turn=turn, conversation_id="c"),
        session=SessionState(conversation_id="c"),
        budget=LLMBudget(4),
    )
    ctx.understanding = QueryUnderstanding(query=turn, canonical_query=turn, intent=intent)
    ctx.products = products or []
    return ctx


def test_plan_uses_pattern_table_without_llm():
    llm = FakeLLM()
    ctx = PlanStage(llm).run(_ctx(intent="browse"))
    assert ctx.plan is not None and ctx.plan.steps[0].inputs["limit"] == 15
    assert llm.calls == []


def test_plan_falls_back_to_llm_for_unknown_intent():
    llm = FakeLLM()
    ctx = PlanStage(llm).run(_ctx(intent="weird"))
    assert ctx.plan is not None and ctx.plan.source == "llm"
    assert llm.calls == ["plan"]


def test_plan_skips_search_when_products_prefilled():
    ctx = PlanStage(FakeLLM()).run(_ctx(products=[Product(title="x")]))
    assert ctx.plan is not None and ctx.plan.steps == []


def test_patterns_do_not_mutate():
    before = PATTERNS["shopping"].model_dump()
    ctx = PlanStage(FakeLLM()).run(_ctx())
    ctx.plan.steps.clear()
    assert PATTERNS["shopping"].model_dump() == before


def test_respond_template_when_budget_gone():
    ctx = _ctx(products=[Product(title="A", price=10.0), Product(title="B", price=20.0)])
    ctx.budget = LLMBudget(max_calls=0)
    ctx = RespondStage(FakeLLM()).run(ctx)
    assert ctx.response is not None and "A ($10.00)" in ctx.response.response
    assert ctx.response.data_count == 2


def test_registry_has_three_tools():
    assert get_registry().names() == ["product_search", "research_product", "review_summarizer"]
