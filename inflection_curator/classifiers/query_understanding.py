"""Query Understanding Module for Inflection Curator.

This module provides query understanding capabilities using multiple LLM
providers (e.g., OpenAI, Claude, Gemini) through LiteLLM. It extracts
structured information from user queries, including intent, products,
categories, and preferences.

Example:
    >>> from inflection_curator.classifiers import QueryUnderstanding
    >>> understander = QueryUnderstanding(provider='openai', model='gpt-4')
    >>> result = understander.analyze_query("I need a gaming laptop under $1500")
    >>> print(result.intent)
    shopping_intent
    >>> print(result.products)
    ['gaming laptop']
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from inflection_curator.classifiers.prompt_manager import PromptManager
from ..constants import PersonaType

try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from ..settings import settings

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysisResult:
    """Structured result from a query understanding analysis.

    Attributes:
        intent (str): The user's intent (e.g., 'shopping_intent').
        confidence (float): The confidence score of the intent prediction.
        products (List[str]): A list of products mentioned in the query.
        category (Optional[str]): The product category, if any.
        budget (Optional[Dict[str, float]]): The user's budget, if mentioned.
        preferences (Dict[str, Any]): Any other preferences mentioned by the user.
        provider_used (str): The provider used for the analysis.
        processing_time_ms (float): The processing time in milliseconds.
    """

    intent: str
    confidence: float
    products: list[str]
    category: str | None = None
    budget: dict[str, float] | None = None
    preferences: dict[str, Any] | None = None
    provider_used: str = ""
    processing_time_ms: float = 0.0

    def __post_init__(self) -> None:
        """Initializes the preferences dictionary if it is None."""
        if self.preferences is None:
            self.preferences = {}

    def to_dict(self) -> dict[str, Any]:
        """Converts the result to a dictionary for JSON serialization."""
        return asdict(self)


class QueryUnderstanding:
    """A query understanding system that uses multiple LLM providers.

    This class extracts structured information from user queries to help the
    shopping assistant provide better recommendations.

    Attributes:
        provider (str): The primary LLM provider (e.g., 'openai', 'claude').
        model (str): The specific model name.
        fallback_providers (List[str]): A list of fallback providers to use if
            the primary provider fails.
        temperature (float): The temperature for the LLM.
        max_tokens (int): The maximum number of tokens for the LLM response.
        allow_fallbacks (bool): Whether to allow falling back to other providers.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4",
        fallback_providers: list[str] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> None:
        """Initializes the query understander.

        Args:
            provider: The primary LLM provider (e.g., 'openai', 'claude').
            model: The specific model name.
            fallback_providers: A list of fallback providers.
            temperature: The LLM temperature (0.0-1.0).
            max_tokens: The maximum number of response tokens.
            **kwargs: Additional keyword arguments.
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is required. Install with: pip install litellm")

        self.provider = provider
        self.model = model
        self.fallback_providers = fallback_providers or []
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allow_fallbacks = kwargs.get("allow_fallbacks", False)
        self._configure_litellm()
        self._persona = kwargs.get("persona", PersonaType.SHOPPER)
        self._prompt_manager = PromptManager()

        logger.info(f"QueryUnderstander initialized with provider: {provider}")

    def _configure_litellm(self) -> None:
        """Configures LiteLLM with API keys from settings."""
        if hasattr(settings, "openai_apikey") and settings.openai_apikey:
            litellm.openai_api_key = settings.openai_apikey

        if hasattr(settings, "anthropic_api_key") and settings.anthropic_api_key:
            litellm.anthropic_api_key = settings.anthropic_api_key

        if hasattr(settings, "gemini_api_key") and settings.gemini_api_key:
            litellm.google_api_key = settings.gemini_api_key

    def analyze_query(self, query: str) -> QueryAnalysisResult | None:
        """Analyzes a user query and extracts structured information.

        Args:
            query: The user's natural language query.

        Returns:
            A `QueryAnalysisResult` object containing the structured analysis
            results, or `None` if the analysis fails.
        """
        start_time = datetime.now()
        prompt = self._prompt_manager.get_prompt(persona=self._persona)
        final_query = prompt.format(query=query)
        # Try primary provider
        result = self._call_llm(self.model, final_query)
        if result:
            result.processing_time_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            return result

        # Try fallback providers
        for fallback_model in self.fallback_providers:
            logger.warning(f"Trying fallback provider: {fallback_model}")
            result = self._call_llm(fallback_model, query)
            if result:
                result.processing_time_ms = (
                    datetime.now() - start_time
                ).total_seconds() * 1000
                return result

        # All providers failed, use fallback analysis
        logger.error("All providers failed, using rule-based fallback")
        return None

    def _call_llm(self, model: str, query: str) -> QueryAnalysisResult | None:
        """Makes a call to the LLM provider.

        Args:
            model: The model identifier.
            query: The user query to analyze.

        Returns:
            A `QueryAnalysisResult` object, or `None` if the call fails.
        """
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": query,
                    },  # query already contains the formatted prompt
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            parsed = json.loads(content)
            return QueryAnalysisResult(
                intent=parsed.get("intent", "information_seeking"),
                confidence=float(parsed.get("confidence", 0.5)),
                products=parsed.get("products", []),
                category=parsed.get("category"),
                budget=parsed.get("budget"),
                preferences=parsed.get("preferences", {}),
                provider_used=model,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {model}: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM call to {model} failed: {e}")
            return None


def create_query_understander(
    provider: str = "openai", model: str | None = None, **kwargs: Any
) -> QueryUnderstanding:
    """Factory function to create a `QueryUnderstanding` instance.

    Args:
        provider: The LLM provider (e.g., 'openai', 'claude', 'gemini').
        model: The specific model name.
        **kwargs: Additional configuration parameters.

    Returns:
        A configured `QueryUnderstanding` instance.
    """
    # Set default models for each provider
    allow_fallbacks = kwargs.get("allow_fallback")
    if model is None:
        model_defaults = {
            "openai": "gpt-4",
            "claude": "claude-3-sonnet-20240229",
            "gemini": "gemini-pro",
        }
        model = model_defaults.get(provider, "gpt-4")

    # Set reasonable fallbacks
    if allow_fallbacks and "fallback_providers" not in kwargs:
        fallback_map = {
            "openai": ["claude-3-sonnet-20240229", "gemini-pro"],
            "claude": ["gpt-4", "gemini-pro"],
            "gemini": ["gpt-4", "claude-3-sonnet-20240229"],
        }
        kwargs["fallback_providers"] = fallback_map.get(provider, [])

    return QueryUnderstanding(provider=provider, model=model, **kwargs)


if __name__ == "__main__":
    # Test the query understander
    understander = create_query_understander(provider="openai", allow_fallbacks=False)

    test_queries = [
        "I need a gaming laptop under $1500",
        "Show me some winter jackets in blue",
        "Looking for running shoes",
        "What's the weather today?",
    ]

    print("Query Understanding Results:")
    print("=" * 40)

    for query in test_queries:
        try:
            result = understander.analyze_query(query)
            if result:
                print(f"\nQuery: {query}")
                print(f"Intent: {result.intent} ({result.confidence:.2f})")
                print(f"Products: {result.products}")
                print(f"Category: {result.category}")
                print(f"Budget: {result.budget}")
                print(f"Provider: {result.provider_used}")
        except Exception as e:
            print(f"Error analyzing '{query}': {e}")
