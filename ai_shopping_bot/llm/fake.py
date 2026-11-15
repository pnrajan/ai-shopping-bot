"""Deterministic LLM for tests and offline development. No network."""

from __future__ import annotations

import re
from typing import TypeVar

from pydantic import BaseModel

from ai_shopping_bot.contracts.context import LLMBudget
from ai_shopping_bot.contracts.plan import ExecutionPlan, ExecutionStep
from ai_shopping_bot.contracts.understanding import (
    Attribute,
    EssentialsIntent,
    GiftIntent,
    QueryUnderstanding,
    RationaleIntent,
    SpecializedIntents,
)
from ai_shopping_bot.settings import ModelRole

T = TypeVar("T", bound=BaseModel)

_PRICE = re.compile(r"(?:under|below|less than|max|up to|around)\s*\$?\s*(\d+(?:\.\d+)?)", re.I)
_VS = re.compile(r"\b(.+?)\s+(?:vs\.?|versus|or)\s+(.+?)(?:\?|$)", re.I)
_ESSENTIALS = re.compile(
    r"what (?:do i|should i|items? (?:do|should) i) (?:need|get|buy|pack)[^.?]*?\b"
    r"(camping|travel|home office|baby|college|moving|kitchen|workout|pet care)\b",
    re.I,
)
_GIFT = re.compile(r"\bgift\b|\bpresent\b|\bfor my (\w+)", re.I)
_RATIONALE = re.compile(r"\bwhy\b|\bexplain\b|\brecommend\b", re.I)
_UNSEARCHABLE = re.compile(
    r"^\s*(i want to buy something|help me shop|hi|hello)\s*[.!?]*\s*$", re.I
)


class FakeLLM:
    """Answers from regexes so the whole pipeline runs offline and deterministically."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        budget: LLMBudget,
        purpose: str,
        schema: type[T] | None = None,
        max_tokens: int = 800,
    ) -> T | str:
        budget.consume(purpose)
        self.calls.append(purpose)
        if schema is QueryUnderstanding:
            return self._understand(user)  # type: ignore[return-value]
        if schema is ExecutionPlan:
            return ExecutionPlan(
                route="product_search",
                steps=[ExecutionStep(tool="product_search", inputs={"limit": 10})],
                source="llm",
            )  # type: ignore[return-value]
        if schema is not None:
            return schema.model_validate(_generic_json(schema))
        return _generic_text(purpose, user)

    @staticmethod
    def _understand(user: str) -> QueryUnderstanding:
        query = user.rsplit("Current turn:", 1)[-1].strip() if "Current turn:" in user else user
        attrs: list[Attribute] = []
        m = _PRICE.search(query)
        if m:
            attrs.append(Attribute(name="max_price", value=m.group(1)))
        intent = "shopping"
        searches = [re.sub(r"\s+", " ", _PRICE.sub("", query)).strip(" .?!")]
        vs = _VS.search(query)
        if vs and len(vs.group(1).split()) <= 6 and len(vs.group(2).split()) <= 6:
            intent = "comparison"
            searches = [vs.group(1).strip(), vs.group(2).strip()]
        ess = _ESSENTIALS.search(query)
        gift = _GIFT.search(query)
        return QueryUnderstanding(
            query=query,
            canonical_query=searches[0],
            intent=intent,
            attributes=attrs,
            search_queries=searches,
            should_ask_followup=bool(_UNSEARCHABLE.match(query)),
            followup_questions=["What kind of product are you looking for?"]
            if _UNSEARCHABLE.match(query)
            else [],
            specialized=SpecializedIntents(
                gift_shopping=GiftIntent(
                    detected=bool(gift), recipient=gift.group(1) if gift and gift.group(1) else None
                ),
                essentials_checklist=EssentialsIntent(
                    detected=bool(ess), topic=ess.group(1).lower() if ess else None
                ),
                product_rationale=RationaleIntent(
                    detected=bool(_RATIONALE.search(query)),
                    criteria=[a.name for a in attrs],
                ),
            ),
            confidence=0.9,
        )


def _generic_json(schema: type[BaseModel]) -> dict:
    out: dict = {}
    for name, field in schema.model_fields.items():
        ann = field.annotation
        if ann is str:
            out[name] = f"fake {name}"
        elif ann is float:
            out[name] = 0.8
        elif ann is bool:
            out[name] = False
        elif getattr(ann, "__origin__", None) is list:
            out[name] = [f"fake {name} 1", f"fake {name} 2"]
        elif getattr(ann, "__origin__", None) is dict:
            out[name] = {}
    return out


def _generic_text(purpose: str, user: str) -> str:
    if purpose.startswith("respond"):
        return "Here are the best matches I found. The top options are listed below with prices."
    if purpose.startswith("essentials"):
        return "Must have:\n- item one\n- item two\nNice to have:\n- item three"
    if purpose.startswith("rationale"):
        return "These match your stated budget and use case."
    if purpose.startswith("compare"):
        return "| Product | Price |\n|---|---|\n| A | $1 |\n| B | $2 |\n\nA suits budget buyers."
    return f"fake response for {purpose}"
