"""Pydantic models for FastAPI service layer.

This module defines the request and response models used by the
FastAPI service layer for type validation and API documentation.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class ShoppingRequest(BaseModel):
    """Request model for shopping queries."""

    query: str = Field(
        ..., min_length=1, max_length=1000, description="The shopping query or request"
    )
    persona: str | None = Field(
        None, description="Persona to use (default, budget_hunter, expert)"
    )
    execution_mode: str | None = Field(None, description="Execution mode to use")
    session_id: str | None = Field(
        None, description="Session ID for context continuity"
    )

    @validator("query")
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "query": "I need wireless headphones under $100",
                "persona": "default",
                "execution_mode": "planned_execution",
                "session_id": "user-123-session",
            }
        }


class QueryUnderstandingData(BaseModel):
    """Query understanding analysis data."""

    intent: str | None = None
    confidence: float | None = None
    products: list[str] | None = None
    category: str | None = None
    budget: dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None


class ProductCandidate(BaseModel):
    """Product candidate information."""

    title: str
    price: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    url: str | None = None
    image_url: str | None = None
    brand: str | None = None
    availability: str | None = None


class ExecutionResult(BaseModel):
    """Execution result data."""

    output: dict[str, Any] | None = None
    clarify: str | None = None
    candidates: list[ProductCandidate] | None = None
    total_found: int | None = None
    execution_time_ms: int | None = None


class ShoppingResponse(BaseModel):
    """Response model for shopping queries."""

    success: bool = True
    route: str
    persona: str
    execution_mode: str
    query_understanding: QueryUnderstandingData | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] | None = None
    execution: ExecutionResult | None = None
    context: dict[str, Any] | None = None
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: int | None = None

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "route": "planned_execution",
                "persona": "shopping.default",
                "execution_mode": "planned_execution",
                "query_understanding": {
                    "intent": "shopping_intent",
                    "confidence": 0.92,
                    "products": ["wireless headphones"],
                    "category": "Electronics",
                    "budget": {"max": 100},
                },
                "execution": {
                    "candidates": [
                        {
                            "title": "Sony WH-CH720N Wireless Headphones",
                            "price": "89.99",
                            "rating": 4.5,
                            "reviews_count": 1250,
                        }
                    ],
                    "total_found": 15,
                },
                "processing_time_ms": 1200,
            }
        }


class PersonaInfo(BaseModel):
    """Persona information model."""

    name: str
    full_name: str
    execution_mode: str
    available_tools: list[str]
    description: str | None = None

    class Config:
        schema_extra = {
            "example": {
                "name": "default",
                "full_name": "shopping.default",
                "execution_mode": "planned_execution",
                "available_tools": [
                    "product_search",
                    "product_reviews",
                    "product_compare",
                ],
                "description": "Balanced shopping assistant for general queries",
            }
        }


class PersonaList(BaseModel):
    """List of available personas."""

    personas: list[str]
    current_persona: str

    class Config:
        schema_extra = {
            "example": {
                "personas": ["default", "budget_hunter", "expert"],
                "current_persona": "default",
            }
        }


class PersonaUpdateRequest(BaseModel):
    """Request to change persona."""

    persona: str = Field(..., description="Persona name to switch to")

    @validator("persona")
    def validate_persona(cls, v):
        if not v or not v.strip():
            raise ValueError("Persona name cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {"example": {"persona": "budget_hunter"}}


class ModeUpdateRequest(BaseModel):
    """Request to change execution mode."""

    mode: str = Field(..., description="Execution mode to switch to")

    @validator("mode")
    def validate_mode(cls, v):
        valid_modes = ["planned_execution", "direct_tool", "llm_then_agent_fallback"]
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of: {', '.join(valid_modes)}")
        return v

    class Config:
        schema_extra = {"example": {"mode": "planned_execution"}}


class SessionContext(BaseModel):
    """Session context information."""

    session_id: str | None = None
    persona: str
    execution_mode: str
    orchestrator_context: dict[str, Any] | None = None
    persona_context: dict[str, Any] | None = None
    created_at: datetime
    last_activity: datetime

    class Config:
        schema_extra = {
            "example": {
                "session_id": "user-123-session",
                "persona": "shopping.default",
                "execution_mode": "planned_execution",
                "created_at": "2024-01-15T10:30:00Z",
                "last_activity": "2024-01-15T10:35:00Z",
            }
        }


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: dict[str, str] = Field(default_factory=dict)
    uptime_seconds: int | None = None

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-01-15T10:30:00Z",
                "services": {
                    "orchestrator": "healthy",
                    "query_understanding": "healthy",
                    "product_provider": "healthy",
                },
                "uptime_seconds": 3600,
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "Invalid persona specified",
                "error_code": "INVALID_PERSONA",
                "details": {
                    "requested_persona": "invalid_persona",
                    "available_personas": ["default", "budget_hunter", "expert"],
                },
            }
        }
