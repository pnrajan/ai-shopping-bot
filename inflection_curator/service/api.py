"""FastAPI application for Inflection Curator shopping assistant.

This module implements the HTTP API service layer that provides
RESTful endpoints for interacting with the shopping orchestrator.

Example:
    >>> from inflection_curator.service import create_app
    >>> app = create_app()
    >>> # Run with: uvicorn inflection_curator.service.api:app --reload
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..core.orchestrator import ShoppingOrchestrator
from ..core.exceptions import OrchestratorError
from .models import (
    ShoppingRequest,
    ShoppingResponse,
    PersonaInfo,
    PersonaList,
    PersonaUpdateRequest,
    ModeUpdateRequest,
    SessionContext,
    HealthStatus,
    ErrorResponse,
    QueryUnderstandingData,
    ExecutionResult,
    ProductCandidate,
)

# Global orchestrator instance and session management
_orchestrator: ShoppingOrchestrator | None = None
_sessions: dict[str, dict[str, Any]] = {}
_startup_time = datetime.utcnow()


def get_orchestrator() -> ShoppingOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ShoppingOrchestrator()
    return _orchestrator


def get_session(session_id: str | None = None) -> dict[str, Any]:
    """Get or create a session."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "orchestrator_context": {},
            "persona_context": {},
        }
    else:
        _sessions[session_id]["last_activity"] = datetime.utcnow()

    return _sessions[session_id]


def cleanup_expired_sessions():
    """Remove expired sessions (older than 24 hours)."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    expired_sessions = [
        sid for sid, session in _sessions.items() if session["last_activity"] < cutoff
    ]
    for sid in expired_sessions:
        del _sessions[sid]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    global _startup_time
    _startup_time = datetime.utcnow()

    # Initialize orchestrator
    get_orchestrator()

    yield

    # Cleanup sessions on shutdown
    _sessions.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Inflection Curator API",
        description="AI Personal Shopping Assistant REST API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="Validation error",
                error_code="VALIDATION_ERROR",
                details={"validation_errors": exc.errors()},
            ).dict(),
        )

    @app.exception_handler(OrchestratorError)
    async def orchestrator_exception_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=str(exc), error_code="ORCHESTRATOR_ERROR"
            ).dict(),
        )

    # Health check endpoint
    @app.get("/health", response_model=HealthStatus, tags=["System"])
    async def health_check():
        """Check the health status of the service and its dependencies."""

        services = {}

        try:
            orch = get_orchestrator()
            services["orchestrator"] = "healthy"

            # Check if QU is available
            if hasattr(orch, "query_understander") and orch.query_understander:
                services["query_understanding"] = "healthy"
            else:
                services["query_understanding"] = "unavailable"

            # Check product provider
            try:
                from ..providers.product_providers import UnWrangleCatalogProvider

                provider = UnWrangleCatalogProvider()
                services["product_provider"] = "healthy"
            except Exception:
                services["product_provider"] = "unavailable"

        except Exception as e:
            services["orchestrator"] = f"unhealthy: {str(e)}"

        uptime = (datetime.utcnow() - _startup_time).total_seconds()

        return HealthStatus(
            status=(
                "healthy" if services.get("orchestrator") == "healthy" else "degraded"
            ),
            services=services,
            uptime_seconds=int(uptime),
        )

    # Main shopping endpoint
    @app.post("/shopping/query", response_model=ShoppingResponse, tags=["Shopping"])
    async def process_shopping_query(
        request: ShoppingRequest, background_tasks: BackgroundTasks
    ):
        """Process a shopping query and return results."""

        start_time = time.time()

        try:
            # Get orchestrator and session
            orch = get_orchestrator()
            session = get_session(request.session_id)

            # Set persona and mode if specified
            if request.persona:
                try:
                    orch.set_persona(request.persona)
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid persona '{request.persona}': {str(e)}",
                    )

            if request.execution_mode:
                try:
                    orch.set_mode(request.execution_mode)
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid execution mode '{request.execution_mode}': {str(e)}",
                    )

            # Process the query
            result = orch.handle(request.query)

            processing_time = int((time.time() - start_time) * 1000)

            # Convert to response format
            response_data = {
                "success": not bool(result.get("error")),
                "route": result.get("route", "unknown"),
                "persona": result.get("persona", "unknown"),
                "execution_mode": (
                    orch.execution_mode.value
                    if hasattr(orch.execution_mode, "value")
                    else str(orch.execution_mode)
                ),
                "attributes": result.get("attributes", {}),
                "plan": result.get("plan"),
                "context": result.get("context"),
                "session_id": session["id"],
                "processing_time_ms": processing_time,
            }

            # Handle query understanding data
            qu_data = result.get("query_understanding")
            if qu_data:
                response_data["query_understanding"] = QueryUnderstandingData(**qu_data)

            # Handle execution results
            execution = result.get("execution", {})
            if execution:
                exec_result = ExecutionResult(
                    output=execution.get("output"), clarify=execution.get("clarify")
                )

                # Convert product candidates if available
                if execution.get("output") and isinstance(execution["output"], dict):
                    candidates_data = execution["output"].get("candidates", [])
                    if candidates_data:
                        candidates = []
                        for candidate in candidates_data:
                            try:
                                candidates.append(ProductCandidate(**candidate))
                            except Exception:
                                # Skip invalid candidates
                                pass
                        exec_result.candidates = candidates
                        exec_result.total_found = len(candidates_data)

                response_data["execution"] = exec_result

            # Handle errors
            if result.get("error"):
                response_data["success"] = False
                response_data["execution"] = ExecutionResult(clarify=result["error"])

            # Schedule session cleanup
            background_tasks.add_task(cleanup_expired_sessions)

            return ShoppingResponse(**response_data)

        except HTTPException:
            raise
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            return ShoppingResponse(
                success=False,
                route="error",
                persona="unknown",
                execution_mode="unknown",
                execution=ExecutionResult(clarify=f"Internal error: {str(e)}"),
                processing_time_ms=processing_time,
            )

    # Persona management endpoints
    @app.get("/personas", response_model=PersonaList, tags=["Personas"])
    async def list_personas():
        """Get list of available personas."""
        orch = get_orchestrator()
        personas = orch.list_personas()
        current_info = orch.get_current_persona_info()

        return PersonaList(
            personas=personas, current_persona=current_info.get("name", "unknown")
        )

    @app.get("/personas/current", response_model=PersonaInfo, tags=["Personas"])
    async def get_current_persona():
        """Get information about the current persona."""
        orch = get_orchestrator()
        info = orch.get_current_persona_info()

        return PersonaInfo(
            name=info.get("name", "unknown"),
            full_name=info.get("full_name", "unknown"),
            execution_mode=info.get("execution_mode", "unknown"),
            available_tools=info.get("available_tools", []),
            description=info.get("description"),
        )

    @app.post("/personas/switch", response_model=PersonaInfo, tags=["Personas"])
    async def switch_persona(request: PersonaUpdateRequest):
        """Switch to a different persona."""
        try:
            orch = get_orchestrator()
            orch.set_persona(request.persona)
            info = orch.get_current_persona_info()

            return PersonaInfo(
                name=info.get("name", "unknown"),
                full_name=info.get("full_name", "unknown"),
                execution_mode=info.get("execution_mode", "unknown"),
                available_tools=info.get("available_tools", []),
                description=info.get("description"),
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to switch persona: {str(e)}",
            )

    # Execution mode management
    @app.post("/mode", tags=["Configuration"])
    async def set_execution_mode(request: ModeUpdateRequest):
        """Change the execution mode."""
        try:
            orch = get_orchestrator()
            orch.set_mode(request.mode)

            return {
                "success": True,
                "mode": (
                    orch.execution_mode.value
                    if hasattr(orch.execution_mode, "value")
                    else str(orch.execution_mode)
                ),
                "message": f"Execution mode changed to {request.mode}",
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to set execution mode: {str(e)}",
            )

    # Session management
    @app.get("/sessions/{session_id}", response_model=SessionContext, tags=["Sessions"])
    async def get_session_info(session_id: str):
        """Get session information."""
        if session_id not in _sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        session = _sessions[session_id]
        orch = get_orchestrator()
        current_persona = orch.get_current_persona_info()

        return SessionContext(
            session_id=session["id"],
            persona=current_persona.get("full_name", "unknown"),
            execution_mode=(
                orch.execution_mode.value
                if hasattr(orch.execution_mode, "value")
                else str(orch.execution_mode)
            ),
            orchestrator_context=session.get("orchestrator_context"),
            persona_context=session.get("persona_context"),
            created_at=session["created_at"],
            last_activity=session["last_activity"],
        )

    @app.delete("/sessions/{session_id}", tags=["Sessions"])
    async def clear_session(session_id: str):
        """Clear a session."""
        if session_id in _sessions:
            del _sessions[session_id]
            return {"success": True, "message": "Session cleared"}

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # System information
    @app.get("/info", tags=["System"])
    async def get_system_info():
        """Get system information."""
        orch = get_orchestrator()
        current_persona = orch.get_current_persona_info()

        return {
            "service": "Inflection Curator API",
            "version": "1.0.0",
            "uptime_seconds": int((datetime.utcnow() - _startup_time).total_seconds()),
            "current_persona": current_persona,
            "execution_mode": (
                orch.execution_mode.value
                if hasattr(orch.execution_mode, "value")
                else str(orch.execution_mode)
            ),
            "available_personas": orch.list_personas(),
            "active_sessions": len(_sessions),
            "timestamp": datetime.utcnow(),
        }

    return app


# Create the default app instance
app = create_app()
