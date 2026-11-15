import pytest

from shopper.contracts.context import LLMBudget, LLMBudgetExceeded
from shopper.contracts.understanding import Attribute, QueryUnderstanding


def test_budget_raises_when_exhausted():
    b = LLMBudget(max_calls=2)
    b.consume("a")
    b.consume("b")
    assert b.remaining == 0
    with pytest.raises(LLMBudgetExceeded):
        b.consume("c")


def test_max_price_parses_currency_text():
    qu = QueryUnderstanding(
        query="x", canonical_query="x", attributes=[Attribute(name="budget", value="$1,500")]
    )
    assert qu.max_price() == 1500.0


def test_max_price_none_when_absent():
    assert QueryUnderstanding(query="x", canonical_query="x").max_price() is None
