"""
Inflection Curator - AI-powered personal shopping assistant.

A comprehensive shopping assistant with multi-provider product search,
intent classification, and persona-based interactions.
"""

__version__ = "1.0.0"
__author__ = "Inflection Team"
__email__ = "team@inflection.ai"

# Core imports for public API
from .core.orchestrator import ShoppingOrchestrator, ShoppingMode
from .personas.shopping import ShoppingPersona, ShoppingPersonaRegistry
from .core.exceptions import CuratorError, PersonaError, PlanningError

__all__ = [
    "__version__",
    "ShoppingOrchestrator",
    "ShoppingMode",
    "ShoppingPersona",
    "ShoppingPersonaRegistry",
    "CuratorError",
    "PersonaError",
    "PlanningError",
]
