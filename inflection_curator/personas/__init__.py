"""Persona system for the Inflection Curator."""

from .shopping import ShoppingPersona, ShoppingPersonaRegistry
from .base import BasePersona

__all__ = [
    "BasePersona",
    "ShoppingPersona",
    "ShoppingPersonaRegistry",
]
