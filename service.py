#!/usr/bin/env python3
"""FastAPI service for Inflection Curator with authentication and persona handling.

This service provides a RESTful API with authentication for the shopping assistant.
The main endpoint /persona/handle processes conversation requests through the
complete orchestrator flow: QueryUnderstanding -> Planner -> Executor -> Response.

Example:
    python service.py
    # Server runs on http://localhost:8000
    # API docs at http://localhost:8000/docs
"""

import os
import sys
import time
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import uvicorn

from inflection_curator import ShoppingOrchestrator


# ============================== AUTHENTICATION ==============================

# Simple API key authentication (in production, use proper JWT/OAuth2)
API_KEYS = {
    "dev-key-123": {"name": "Development", "permissions": ["read", "write"]},
    "prod-key-456": {"name": "Production", "permissions": ["read", "write"]},
    # Add more API keys as needed
}

# Bearer token security scheme
security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def authenticate_api_key(api_key: str | None = Security(api_key_header)):
    """Authenticate using API key in header."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return API_KEYS[api_key]


async def authenticate_bearer(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Authenticate using Bearer token."""
    token = credentials.credentials

    if token not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return API_KEYS[token]


class ConversationInput(BaseModel):
    """Input payload for the /persona/handle endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User query or conversation input",
    )
    persona: str | None = Field(
        "default", description="Persona to use (default, budget_hunter, expert)"
    )
    session_id: str | None = Field(
        None, description="Session ID for conversation continuity"
    )
    context: dict[str, Any] | None = Field(
        None, description="Additional context data"
    )
    execution_mode: str | None = Field(
        "planned_execution", description="Execution mode"
    )

    @validator("query")
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()

    @validator("persona")
    def validate_persona(cls, v):
        if v and v not in ["default", "budget_hunter", "expert"]:
            raise ValueError("Persona must be one of: default, budget_hunter, expert")
        return v or "default"

    class Config:
        schema_extra = {
            "example": {
                "query": "I need wireless headphones under $100 for working out",
                "persona": "budget_hunter",
                "session_id": "user-abc-123",
                "context": {
                    "user_preferences": {
                        "budget_conscious": True,
                        "activity": "fitness",
                    }
                },
                "execution_mode": "planned_execution",
            }
        }


class QueryUnderstandingResult(BaseModel):
    """Query Understanding analysis result."""

    intent: str | None = None
    confidence: float | None = None
    products: list[str] | None = None
    category: str | None = None
    budget: dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None
    analysis_time_ms: int | None = None


class PlanningResult(BaseModel):
    """Planning stage result."""

    steps: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    clarify: str | None = None
    reason: str | None = None
    planning_time_ms: int | None = None


class ExecutionResult(BaseModel):
    """Execution stage result."""

    success: bool = True
    output: dict[str, Any] | None = None
    clarify: str | None = None
    candidates: list[dict[str, Any]] | None = None
    total_found: int | None = None
    execution_time_ms: int | None = None
    tools_used: list[str] | None = None


class PersonaHandleResponse(BaseModel):
    """Complete response from /persona/handle endpoint."""

    success: bool = True
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None
    persona: str
    execution_mode: str

    # Flow stages
    query_understanding: QueryUnderstandingResult | None = None
    planning: PlanningResult | None = None
    execution: ExecutionResult | None = None

    # Response data
    response_message: str | None = None
    recommendations: list[dict[str, Any]] | None = None

    # Metadata
    total_processing_time_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    flow_trace: list[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "request_id": "req-abc-123",
                "session_id": "user-abc-123",
                "persona": "budget_hunter",
                "execution_mode": "planned_execution",
                "query_understanding": {
                    "intent": "shopping_intent",
                    "confidence": 0.92,
                    "products": ["wireless headphones"],
                    "category": "Electronics",
                    "budget": {"max": 100},
                },
                "planning": {
                    "steps": [
                        {
                            "tool": "product_search",
                            "args": {"query": "wireless headphones", "budget_max": 100},
                        }
                    ],
                    "confidence": 0.85,
                },
                "execution": {
                    "success": True,
                    "total_found": 15,
                    "candidates": [
                        {
                            "title": "Sony WH-CH720N Wireless Headphones",
                            "price": "89.99",
                            "rating": 4.5,
                        }
                    ],
                },
                "response_message": "Found 15 budget-friendly wireless headphones under $100",
                "total_processing_time_ms": 1250,
                "flow_trace": [
                    "query_understanding",
                    "planning",
                    "execution",
                    "response_generation",
                ],
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================== FASTAPI APPLICATION ==============================

app = FastAPI(
    title="Inflection Curator API",
    description="AI Personal Shopping Assistant with Authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
_orchestrator: ShoppingOrchestrator | None = None


def get_orchestrator() -> ShoppingOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ShoppingOrchestrator()
    return _orchestrator


# ============================== API ENDPOINTS ==============================


@app.get("/health")
async def health_check():
    """Health check endpoint - no authentication required."""
    return {
        "status": "healthy",
        "service": "Inflection Curator API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow(),
    }


@app.get("/auth/test")
async def test_auth(user_info=Depends(authenticate_api_key)):
    """Test authentication endpoint."""
    return {
        "message": "Authentication successful",
        "user": user_info,
        "timestamp": datetime.utcnow(),
    }


@app.post("/persona/handle", response_model=PersonaHandleResponse)
async def handle_conversation(
    payload: ConversationInput, user_info=Depends(authenticate_api_key)
):
    """
    Main conversation handling endpoint.

    Flow: Orchestrator -> QueryUnderstanding -> Planner -> Executor -> Response

    This endpoint processes conversation input through the complete orchestrator
    pipeline and returns detailed results from each stage of processing.
    """

    start_time = time.time()
    flow_trace = []

    try:
        # Initialize orchestrator
        orch = get_orchestrator()
        flow_trace.append("orchestrator_init")

        # Set persona if specified
        if payload.persona and payload.persona != "default":
            try:
                orch.set_persona(payload.persona)
                flow_trace.append(f"persona_set:{payload.persona}")
            except Exception as e:
                return PersonaHandleResponse(
                    success=False,
                    persona="unknown",
                    execution_mode="unknown",
                    execution=ExecutionResult(
                        success=False,
                        clarify=f"Failed to set persona '{payload.persona}': {str(e)}",
                    ),
                    total_processing_time_ms=int((time.time() - start_time) * 1000),
                    flow_trace=flow_trace,
                )
        # if the persona is not set, find the last persona used and set up the context to continue the confirmation
        # TODO (pankaj)
        # Set execution mode if specified
        if payload.execution_mode:
            try:
                orch.set_mode(payload.execution_mode)
                flow_trace.append(f"mode_set:{payload.execution_mode}")
            except Exception as e:
                return PersonaHandleResponse(
                    success=False,
                    persona=orch.get_current_persona_info().get("full_name", "unknown"),
                    execution_mode="unknown",
                    execution=ExecutionResult(
                        success=False,
                        clarify=f"Failed to set execution mode '{payload.execution_mode}': {str(e)}",
                    ),
                    total_processing_time_ms=int((time.time() - start_time) * 1000),
                    flow_trace=flow_trace,
                )

        # Get current persona info
        persona_info = orch.get_current_persona_info()
        current_persona = persona_info.get("full_name", "unknown")
        current_mode = (
            orch.execution_mode.value
            if hasattr(orch.execution_mode, "value")
            else str(orch.execution_mode)
        )

        # Process through orchestrator - this handles the complete flow
        flow_trace.append("orchestrator_processing")
        result = orch.handle(payload.query)

        processing_time = int((time.time() - start_time) * 1000)

        # Extract results from orchestrator response
        qu_result = None
        if result.get("query_understanding"):
            qu_data = result["query_understanding"]
            qu_result = QueryUnderstandingResult(
                intent=qu_data.get("intent"),
                confidence=qu_data.get("confidence"),
                products=qu_data.get("products"),
                category=qu_data.get("category"),
                budget=qu_data.get("budget"),
                preferences=qu_data.get("preferences"),
            )
            flow_trace.append("query_understanding")

        # Extract planning results
        planning_result = None
        if result.get("plan"):
            plan_data = result["plan"]
            planning_result = PlanningResult(
                steps=plan_data.get("steps", []),
                confidence=plan_data.get("confidence"),
                clarify=plan_data.get("clarify"),
                reason=plan_data.get("reason"),
            )
            flow_trace.append("planning")

        # Extract execution results
        execution_result = None
        if result.get("execution"):
            exec_data = result["execution"]
            execution_result = ExecutionResult(
                success=not bool(result.get("error")),
                output=exec_data.get("output"),
                clarify=exec_data.get("clarify"),
                total_found=(
                    exec_data.get("output", {}).get("total_found")
                    if exec_data.get("output")
                    else None
                ),
            )

            # Extract candidates if available
            if exec_data.get("output") and isinstance(exec_data["output"], dict):
                candidates = exec_data["output"].get("candidates", [])
                if candidates:
                    execution_result.candidates = candidates[
                        :10
                    ]  # Limit to 10 for response size
                    execution_result.total_found = len(candidates)

            flow_trace.append("execution")

        # Generate response message
        response_message = None
        recommendations = None

        if result.get("error"):
            response_message = f"Error: {result['error']}"
        elif execution_result and execution_result.candidates:
            response_message = f"Found {execution_result.total_found or len(execution_result.candidates)} products matching your request"
            recommendations = execution_result.candidates[:5]  # Top 5 recommendations
        elif execution_result and execution_result.clarify:
            response_message = execution_result.clarify
        else:
            response_message = "I processed your request but didn't find specific products to recommend."

        flow_trace.append("response_generation")

        return PersonaHandleResponse(
            success=not bool(result.get("error")),
            session_id=payload.session_id,
            persona=current_persona,
            execution_mode=current_mode,
            query_understanding=qu_result,
            planning=planning_result,
            execution=execution_result,
            response_message=response_message,
            recommendations=recommendations,
            total_processing_time_ms=processing_time,
            flow_trace=flow_trace,
        )

    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        flow_trace.append("error")

        return PersonaHandleResponse(
            success=False,
            persona="unknown",
            execution_mode="unknown",
            execution=ExecutionResult(
                success=False, clarify=f"Internal error: {str(e)}"
            ),
            response_message=f"Sorry, I encountered an error: {str(e)}",
            total_processing_time_ms=processing_time,
            flow_trace=flow_trace,
        )


@app.get("/personas", dependencies=[Depends(authenticate_api_key)])
async def list_personas():
    """Get list of available personas."""
    orch = get_orchestrator()
    return {
        "personas": orch.list_personas(),
        "current_persona": orch.get_current_persona_info().get("name", "unknown"),
    }


@app.get("/info", dependencies=[Depends(authenticate_api_key)])
async def get_service_info():
    """Get service information."""
    orch = get_orchestrator()
    return {
        "service": "Inflection Curator API",
        "version": "1.0.0",
        "current_persona": orch.get_current_persona_info(),
        "execution_mode": (
            orch.execution_mode.value
            if hasattr(orch.execution_mode, "value")
            else str(orch.execution_mode)
        ),
        "available_personas": orch.list_personas(),
        "authentication": "API Key required",
        "main_endpoint": "/persona/handle",
        "timestamp": datetime.utcnow(),
    }


# ============================== ERROR HANDLERS ==============================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail, error_code=f"HTTP_{exc.status_code}"
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            error_code="INTERNAL_ERROR",
            details={"exception": str(exc)},
        ).dict(),
    )


# ============================== MAIN ENTRY POINT ==============================


def main():
    """Main entry point for the service."""
    print("🚀 Starting Inflection Curator API Service")
    print("=" * 50)
    print(f"📍 Server: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    print(f"🔑 Authentication: API Key required (X-API-Key header)")
    print(f"🎯 Main Endpoint: POST /persona/handle")
    print()
    print("Available API Keys for testing:")
    for key, info in API_KEYS.items():
        print(f"  - {key} ({info['name']})")
    print()

    # Check environment variables
    required_vars = ["OPENAI_API_KEY", "UNWRANGLE_APIKEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("   Some features may not work properly.")
    else:
        print("✅ All required environment variables are set")

    print("\n🔄 Starting server...")

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", access_log=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down service")
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
