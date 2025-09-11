"""
Base persona class for the Inflection Curator.

This module defines the abstract base class for all personas in the system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class PersonaConfig:
    """Base configuration for personas."""

    name: str
    variant: str
    description: str

    @property
    def full_name(self) -> str:
        return f"{self.name}.{self.variant}"


class BasePersona(ABC):
    """Abstract base class for all personas."""

    def __init__(self, config: PersonaConfig):
        self.config = config
        self._session_context: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def variant(self) -> str:
        return self.config.variant

    @property
    def full_name(self) -> str:
        return self.config.full_name

    @abstractmethod
    def parse_user_input(self, user_input: str) -> dict[str, Any]:
        """Parse user input into structured attributes."""
        pass

    @abstractmethod
    def plan_execution(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Generate an execution plan from parsed attributes."""
        pass

    @abstractmethod
    def get_available_tools(self) -> dict[str, Any]:
        """Get available tools for this persona."""
        pass

    def get_session_context(self) -> dict[str, Any]:
        """Get current session context."""
        return self._session_context.copy()

    def clear_session_context(self) -> None:
        """Clear session context."""
        self._session_context.clear()

    def update_session_context(self, **kwargs) -> None:
        """Update session context with new values."""
        self._session_context.update(kwargs)
