"""Tool input and output contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ai_shopping_bot.contracts.chat import Turn
from ai_shopping_bot.contracts.understanding import QueryUnderstanding


class ToolInput(BaseModel):
    understanding: QueryUnderstanding
    turns: list[Turn] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class ToolOutput(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
