"""Output of the query-understanding stage. One structured LLM call fills this."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Attribute(BaseModel):
    name: str
    value: str


class GiftIntent(BaseModel):
    detected: bool = False
    recipient: str | None = None
    needs_clarification: bool = False


class EssentialsIntent(BaseModel):
    detected: bool = False
    topic: str | None = None


class RationaleIntent(BaseModel):
    detected: bool = False
    criteria: list[str] = Field(default_factory=list)


class SpecializedIntents(BaseModel):
    gift_shopping: GiftIntent = Field(default_factory=GiftIntent)
    essentials_checklist: EssentialsIntent = Field(default_factory=EssentialsIntent)
    product_rationale: RationaleIntent = Field(default_factory=RationaleIntent)


class QueryUnderstanding(BaseModel):
    query: str
    canonical_query: str
    intent: str = Field("shopping", description="shopping | comparison | browse | other")
    category: str | None = None
    attributes: list[Attribute] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    should_ask_followup: bool = False
    followup_questions: list[str] = Field(default_factory=list)
    is_continuation: bool = False
    specialized: SpecializedIntents = Field(default_factory=SpecializedIntents)
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    def attribute(self, name: str) -> str | None:
        return next((a.value for a in self.attributes if a.name == name), None)

    def max_price(self) -> float | None:
        raw = self.attribute("max_price") or self.attribute("budget")
        if not raw:
            return None
        digits = "".join(c for c in raw if c.isdigit() or c == ".")
        try:
            return float(digits) if digits else None
        except ValueError:
            return None
