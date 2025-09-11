"""Prompt Manager for Query Understanding.

This module provides prompt templates for different personas and query understanding tasks.
"""

from typing import Dict, Any
from ..constants import PersonaType


class PromptManager:
    """Manages prompt templates for query understanding across different personas."""

    def __init__(self):
        self.templates = {
            PersonaType.SHOPPER: """
You are a shopping query understanding system. Extract structured information from user queries.

Return exactly one JSON object with these fields:
- intent: The user's intent (e.g., 'shopping_intent', 'product_search', 'price_inquiry')
- confidence: Confidence score 0.0-1.0
- products: Array of products mentioned
- category: Product category (Electronics, Apparel, Furniture, or null)
- budget: Dictionary with min/max budget if mentioned (e.g., {{"min": 50, "max": 200}})
- preferences: Dictionary of other preferences (color, size, brand, features)

Query to analyze: {query}

Return only valid JSON, no other text.
"""
        }

    def get_prompt(self, persona: str = PersonaType.SHOPPER) -> str:
        """Get prompt template for a specific persona."""
        return self.templates.get(persona, self.templates[PersonaType.SHOPPER])
