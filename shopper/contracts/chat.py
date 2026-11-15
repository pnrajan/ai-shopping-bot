"""Chat request and response models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Turn(BaseModel):
    role: Role
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    recent_turn: str = Field(..., min_length=1, max_length=2000, description="Latest user message")
    history: list[Turn] = Field(default_factory=list, description="Prior turns, oldest first")
    conversation_id: str = Field(..., min_length=1, max_length=128)


class DataType(str, Enum):
    PRODUCTS = "products"
    GENERAL = "general"
    CLARIFICATION = "clarification"


class ChatResponse(BaseModel):
    success: bool = True
    response: str
    conversation_id: str
    data: list[dict[str, Any]] = Field(default_factory=list)
    data_type: DataType = DataType.GENERAL
    data_count: int = 0
    clarification_questions: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
