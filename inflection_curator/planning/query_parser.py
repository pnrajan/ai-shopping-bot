"""Shopping Query Parser for Inflection Curator.

This module implements the ShoppingQueryParser class, which is responsible for
converting natural language shopping queries into structured attributes. This is
the first step in the planning pipeline and is crucial for understanding the
user's intent.

Example:
    >>> from inflection_curator.planning import ShoppingQueryParser
    >>> parser = ShoppingQueryParser()
    >>> user_query = "I'm looking for a new laptop under $1000"
    >>> attrs = parser.parse(user_query, persona)
    >>> print(attrs)
"""

import json
import time
from typing import Dict, Any
from litellm import completion, RateLimitError, APIConnectionError, APIError
from ..utils.config import MODEL_PARSER, LITELLM_TIMEOUT, LITELLM_RETRIES


class ShoppingQueryParser:
    """Extracts structured information from user queries using an LLM.

    This class takes natural language shopping queries and converts them into
    structured attributes that can be used by the planner and executor.

    Attributes:
        model (str): The name of the language model to use for parsing.
    """

    def __init__(self, model: str = MODEL_PARSER) -> None:
        """Initializes the ShoppingQueryParser.

        Args:
            model: The name of the language model to use for parsing.
        """
        self.model = model

    def parse(self, user_query: str, persona: Any) -> dict[str, Any]:
        """Parses a user query into structured attributes.

        This method uses a persona-specific prompt to guide the LLM in
        extracting the relevant information from the user's query.

        Args:
            user_query: The raw user input string.
            persona: The persona object, which contains the parser system prompt.

        Returns:
            A dictionary containing the structured attributes extracted from the
            query.
        """
        if not user_query or not user_query.strip():
            return self._get_empty_result(user_query, "Empty query")

        # Use persona's parser system prompt
        parser_prompt = persona.config.parser_prompt

        err = None
        for attempt in range(max(1, LITELLM_RETRIES + 1)):
            try:
                resp = completion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": parser_prompt},
                        {"role": "user", "content": user_query},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=600,
                    timeout=LITELLM_TIMEOUT,
                )

                # Parse the JSON response
                parsed = json.loads(resp.choices[0].message.content)

                # Ensure consistent structure with defaults
                result = {
                    "query": parsed.get("query", ""),
                    "category": parsed.get("category"),
                    "brands": parsed.get("brands", []),
                    "attributes": parsed.get("attributes", []),
                    "size": parsed.get("size"),
                    "color": parsed.get("color"),
                    "budget_min": parsed.get("budget_min"),
                    "budget_max": parsed.get("budget_max"),
                    "products": parsed.get("products", []),
                    "confidence": max(0.0, min(1.0, parsed.get("confidence", 0.5))),
                    "raw_input": user_query,
                }

                # Clean up the data
                result = self._clean_parsed_result(result)

                return result

            except (RateLimitError, APIConnectionError, APIError, TimeoutError) as e:
                err = e
                if attempt < LITELLM_RETRIES:
                    time.sleep(0.5)  # Brief retry delay
            except json.JSONDecodeError as e:
                err = f"Invalid JSON response: {e}"
                break  # Don't retry JSON errors
            except Exception as e:
                err = e
                break  # Don't retry unexpected errors

        # Return fallback result if all attempts failed
        return self._get_empty_result(user_query, f"Parser error: {err}")

    def _clean_parsed_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Cleans and validates the parsed result.

        Args:
            result: The parsed result from the LLM.

        Returns:
            The cleaned and validated result.
        """
        # Ensure arrays are actually arrays
        for field in ["brands", "attributes", "products"]:
            if not isinstance(result.get(field), list):
                result[field] = []

        # Ensure budget values are numbers or None
        for field in ["budget_min", "budget_max"]:
            value = result.get(field)
            if value is not None:
                try:
                    result[field] = float(value) if value != "" else None
                except (ValueError, TypeError):
                    result[field] = None

        # Clean string fields
        for field in ["query", "category", "size", "color"]:
            value = result.get(field)
            if isinstance(value, str):
                result[field] = value.strip() if value.strip() else None
            elif value == "":
                result[field] = None

        # Ensure confidence is valid
        confidence = result.get("confidence", 0.5)
        try:
            result["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            result["confidence"] = 0.5

        return result

    def _get_empty_result(self, user_query: str, error_reason: str) -> dict[str, Any]:
        """Returns a basic fallback result when parsing fails.

        Args:
            user_query: The original user query.
            error_reason: The reason for the parsing failure.

        Returns:
            A dictionary with default values and an error message.
        """
        return {
            "query": user_query.strip() if user_query else "",
            "category": None,
            "brands": [],
            "attributes": [],
            "size": None,
            "color": None,
            "budget_min": None,
            "budget_max": None,
            "products": [],
            "confidence": 0.3,
            "raw_input": user_query,
            "parse_error": error_reason,
        }
