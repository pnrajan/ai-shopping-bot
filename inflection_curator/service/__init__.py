"""FastAPI service layer for Inflection Curator.

This module provides HTTP API endpoints for the shopping assistant,
enabling web applications and external services to interact with
the orchestrator through RESTful APIs.

Example:
    >>> from inflection_curator.service import create_app
    >>> app = create_app()
    >>> # Run with uvicorn app:app --reload
"""

from .api import create_app
from .models import ShoppingRequest, ShoppingResponse, PersonaInfo, ErrorResponse

__all__ = [
    "create_app",
    "ShoppingRequest",
    "ShoppingResponse",
    "PersonaInfo",
    "ErrorResponse",
]
