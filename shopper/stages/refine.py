"""Stage 2: if the session holds products and this turn narrows them, filter instead of searching.

Regex runs first because it is free and deterministic. The LLM is consulted only when regex sees
nothing and the understanding stage flagged the turn as a continuation.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from shopper.contracts.context import RequestContext
from shopper.contracts.product import Product
from shopper.llm.client import LLMClient, LLMError
from shopper.search import filters
from shopper.settings import ModelRole
from shopper.stages.base import finish_with_products

_PRICE_MAX = re.compile(
    r"\b(?:under|less than|below|cheaper than|no more than|max(?:imum)?)\s*\$?\s?(\d+(?:\.\d+)?)"
)
_PRICE_MIN = re.compile(r"\b(?:over|more than|above|at least|min(?:imum)?)\s*\$?\s?(\d+(?:\.\d+)?)")
_POINTERS = re.compile(
    r"\b(?:from|out of|of)\s+(?:those|these|them|the ones?)\b|\bwhich (?:one|ones?)\b"
    r"|\b(?:narrow|filter|only|just)\b"
)
_FEATURE = re.compile(
    r"\b(?:with|having|that (?:have|has)|featuring)\s+([\w\- ]{3,40}?)(?=[,.?!]|$| and\b)"
)


class RefinementCriteria(BaseModel):
    is_refinement: bool = False
    price_max: float | None = None
    price_min: float | None = None
    features: list[str] = Field(default_factory=list)
    reasoning: str = ""


def detect_with_regex(query: str) -> RefinementCriteria | None:
    q = query.lower()
    crit = RefinementCriteria()
    if m := _PRICE_MAX.search(q):
        crit.price_max = float(m.group(1))
    if m := _PRICE_MIN.search(q):
        crit.price_min = float(m.group(1))
    crit.features = [f.strip() for f in _FEATURE.findall(q)]
    pointer = bool(_POINTERS.search(q))
    if not (pointer or crit.price_max is not None or crit.price_min is not None or crit.features):
        return None
    crit.is_refinement = True
    parts = []
    if crit.price_max is not None:
        parts.append(f"price ≤ ${crit.price_max:g}")
    if crit.price_min is not None:
        parts.append(f"price ≥ ${crit.price_min:g}")
    if crit.features:
        parts.append("features: " + ", ".join(crit.features))
    crit.reasoning = "; ".join(parts) or "narrowing previous results"
    return crit


def apply(products: list[Product], crit: RefinementCriteria) -> list[Product]:
    out = products
    if crit.price_max is not None:
        out = filters.by_max_price(out, crit.price_max)
    if crit.price_min is not None:
        out = filters.by_min_price(out, crit.price_min)
    if crit.features:
        out = filters.by_features(out, crit.features)
    return out


class RefineStage:
    name = "refine"

    def __init__(self, llm: LLMClient | None = None):
        self._llm = llm

    def run(self, ctx: RequestContext) -> RequestContext:
        stored = ctx.session.last_products
        if not stored or ctx.understanding is None:
            return ctx
        if ctx.understanding.intent == "comparison":
            return ctx
        crit = detect_with_regex(ctx.request.recent_turn)
        if (
            crit is None
            and self._llm
            and ctx.understanding.is_continuation
            and ctx.budget.remaining > 2
        ):
            crit = self._detect_with_llm(ctx)
        if crit is None or not crit.is_refinement:
            return ctx
        ctx.products = apply(stored, crit)
        ctx.extras["refinement"] = crit.reasoning
        ctx.done = True
        if not ctx.products:
            return finish_with_products(
                ctx,
                f"None of the products I showed match {crit.reasoning}. "
                "Want me to search again with those criteria?",
                note="refinement:no-match",
            )
        n = len(ctx.products)
        lead = (
            f"Here is the one that matches {crit.reasoning}."
            if n == 1
            else f"Here are {n} of the previous products matching {crit.reasoning}."
        )
        return finish_with_products(ctx, lead, note="refinement")

    def _detect_with_llm(self, ctx: RequestContext) -> RefinementCriteria | None:
        assert self._llm is not None
        try:
            result = self._llm.complete(
                role=ModelRole.UNDERSTANDING,
                system=(
                    "The user previously saw a list of products. Decide whether this new message "
                    "narrows that list (is_refinement) and extract price_max, price_min, features."
                ),
                user=ctx.request.recent_turn,
                budget=ctx.budget,
                purpose="refine.detect",
                schema=RefinementCriteria,
                max_tokens=200,
            )
        except LLMError:
            return None
        return result if isinstance(result, RefinementCriteria) else None
