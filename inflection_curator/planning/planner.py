"""Shopping Planner for Inflection Curator.

This module implements the ShoppingPlanner class, which is responsible for
generating execution plans based on structured query attributes. The planner
uses a large language model (LLM) to determine the most appropriate tool to use
and the arguments to pass to it.

Example:
    >>> from inflection_curator.planning import ShoppingPlanner
    >>> registry_summary = {
    ...     "product_search": {"requires": [], "requires_any": ["query"]}
    ... }
    >>> planner = ShoppingPlanner(registry_summary)
    >>> attrs = {"query": "laptop"}
    >>> plan = planner.build(attrs, {}, persona)
    >>> print(plan)
"""

import json
import time
import math
from typing import Dict, Any
from litellm import completion, RateLimitError, APIConnectionError, APIError
from ..utils.config import MODEL_PLANNER, LITELLM_TIMEOUT, LITELLM_RETRIES


def _clamp01(x: Any) -> float:
    """Clamps a value to the [0.0, 1.0] range.

    Args:
        x: The value to clamp.

    Returns:
        The clamped value as a float.
    """
    try:
        f = float(x)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return 0.0


class ShoppingPlanner:
    """Generates execution plans from query attributes using an LLM.

    This class takes structured attributes from the query parser and generates a
    single-step plan with the appropriate tool and arguments.

    Attributes:
        model (str): The name of the language model to use for planning.
        registry_summary (Dict[str, Dict[str, Any]]): A summary of the available
            tools and their requirements.
    """

    def __init__(
        self, registry_summary: dict[str, dict[str, Any]], model: str = MODEL_PLANNER
    ) -> None:
        """Initializes the ShoppingPlanner.

        Args:
            registry_summary: A summary of the available tools and their
                requirements.
            model: The name of the language model to use for planning.
        """
        self.model = model
        self.registry_summary = registry_summary

    def build(
        self, attrs: dict[str, Any], session_ctx: dict[str, Any], persona: Any
    ) -> dict[str, Any]:
        """Builds an execution plan from parsed attributes and context.

        Args:
            attrs: The structured query attributes from the parser or QU system.
            session_ctx: The session context, including previous selections.
            persona: The persona object, which contains the planner system prompt.

        Returns:
            A dictionary containing the execution plan, including the steps to
            take, a confidence score, a clarification message if needed, and
            the reasoning behind the plan.
        """
        # Build enhanced prompt structure with QU context if available
        prompt = {
            "registry": self.registry_summary,
            "attributes": attrs,
            "context": {
                "last_selected_product": session_ctx.get("last_selected_product")
            },
            "constraints": {
                "max_steps": 1,
                "ask_when_missing": True,
                "avoid_fabrication": True,
            },
        }

        # Add QU insights if available
        if "_qu_confidence" in attrs and "_qu_intent" in attrs:
            prompt["query_understanding"] = {
                "intent": attrs["_qu_intent"],
                "confidence": attrs["_qu_confidence"],
                "analysis_quality": (
                    "high" if attrs["_qu_confidence"] > 0.7 else "medium"
                ),
            }

        err = None
        for attempt in range(max(1, LITELLM_RETRIES + 1)):
            try:
                resp = completion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": persona.config.planner_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(prompt, ensure_ascii=False),
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=600,
                    timeout=LITELLM_TIMEOUT,
                )

                # Parse and validate the response
                data = json.loads(resp.choices[0].message.content)

                # Ensure single step constraint
                data["steps"] = (data.get("steps") or [])[:1]

                # Validate confidence score
                data["confidence"] = _clamp01(data.get("confidence", 0.0))

                # Ensure reason is present
                data["reason"] = str(data.get("reason", ""))

                return data

            except (RateLimitError, APIConnectionError, APIError, TimeoutError) as e:
                err = e
                if attempt < LITELLM_RETRIES:
                    time.sleep(0.5)  # Brief retry delay
            except Exception as e:
                err = e
                break  # Don't retry unexpected errors

        # Return fallback plan if all attempts failed
        return {
            "steps": [],
            "confidence": 0.45,
            "clarify": "What product are you interested in?",
            "reason": f"planner error: {err}",
        }
