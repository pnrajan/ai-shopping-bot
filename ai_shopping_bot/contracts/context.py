"""Request context carried through every pipeline stage."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ai_shopping_bot.contracts.chat import ChatRequest, ChatResponse
from ai_shopping_bot.contracts.plan import ExecutionPlan, ExecutionResponse
from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.contracts.understanding import QueryUnderstanding


class LLMBudgetExceeded(RuntimeError):
    pass


@dataclass
class LLMBudget:
    max_calls: int
    used: int = 0

    def consume(self, purpose: str) -> None:
        if self.used >= self.max_calls:
            raise LLMBudgetExceeded(f"LLM budget of {self.max_calls} exhausted at '{purpose}'")
        self.used += 1

    @property
    def remaining(self) -> int:
        return self.max_calls - self.used


class StageEvent(BaseModel):
    stage: str
    ms: int
    note: str = ""


class SessionState(BaseModel):
    conversation_id: str
    turns: list[dict[str, str]] = []
    last_products: list[Product] = []
    clarifications_asked: int = 0
    updated_at: float = 0.0


@dataclass
class RequestContext:
    request: ChatRequest
    session: SessionState
    budget: LLMBudget
    understanding: QueryUnderstanding | None = None
    plan: ExecutionPlan | None = None
    execution: ExecutionResponse | None = None
    products: list[Product] = field(default_factory=list)
    reply: str = ""
    response: ChatResponse | None = None
    trace: list[StageEvent] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    done: bool = False
    started: float = field(default_factory=time.perf_counter)

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)
