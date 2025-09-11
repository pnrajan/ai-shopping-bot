"""Shopping Persona for Inflection Curator.

This module defines the shopping persona, including its configuration, tools,
and the logic for parsing user input, planning, and executing shopping-related
tasks. It provides a complete, self-contained system for handling shopping
requests with different persona variants.

Example:
    >>> from inflection_curator.personas import ShoppingPersonaRegistry
    >>> registry = ShoppingPersonaRegistry()
    >>> persona = registry.get_persona("default")
    >>> user_input = "I need a new laptop"
    >>> attrs = persona.parse_user_input(user_input)
    >>> plan = persona.plan_execution(attrs)
    >>> result = persona.execute_tool(plan['steps'][0]['tool'], **plan['steps'][0]['args'])
    >>> print(result)
"""

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import yaml
from pathlib import Path

from litellm import completion, RateLimitError, APIConnectionError, APIError
from ..utils.config import MODEL_PARSER, MODEL_PLANNER, LITELLM_TIMEOUT, LITELLM_RETRIES
from ..providers.product_providers import UnWrangleCatalogProvider
from ..utils.logger import audit_event


@dataclass
class ShoppingConfig:
    """Configuration for shopping persona variants.

    This dataclass holds the configuration for a specific shopping persona
    variant, including the prompts for the AI models, behavior settings, and
    tool configurations.

    Attributes:
        name (str): The name of the persona.
        variant (str): The variant of the persona (e.g., "default",
            "budget_hunter").
        parser_prompt (str): The prompt for the query parser model.
        planner_prompt (str): The prompt for the planner model.
        agent_prompt (str): The prompt for the agent model.
        style (Dict[str, Any]): Behavior settings for the persona's style.
        policies (Dict[str, Any]): Policies that guide the persona's decisions.
        capabilities (List[str]): A list of the persona's capabilities.
        enabled_tools (List[str]): A list of the tools enabled for this persona.
        tool_configs (Dict[str, Dict[str, Any]]): Configuration for each tool.
        providers (Dict[str, List[str]]): Configuration for data providers.
    """

    name: str
    variant: str

    # AI model configurations
    parser_prompt: str
    planner_prompt: str
    agent_prompt: str

    # Behavior settings
    style: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)

    # Tool and provider configurations
    enabled_tools: list[str] = field(default_factory=list)
    tool_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    providers: dict[str, list[str]] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Returns the full name of the persona variant."""
        return f"shopping.{self.variant}"


class ShoppingTool(ABC):
    """Base class for all shopping-specific tools.

    This abstract base class defines the interface for all shopping tools. It
    provides a common structure for executing tools, validating inputs, and
    defining the tool's schema and description.

    Attributes:
        config (Optional[Dict[str, Any]]): The configuration for the tool.
        name (str): The name of the tool.
        execution_count (int): The number of times the tool has been executed.
        last_execution_time (Optional[float]): The timestamp of the last
            execution.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initializes the ShoppingTool.

        Args:
            config: The configuration for the tool.
        """
        self.config = config or {}
        self.name = self._get_tool_name()
        self.execution_count = 0
        self.last_execution_time = None

    def _get_tool_name(self) -> str:
        """Generates the tool name from the class name."""
        class_name = self.__class__.__name__
        if class_name.endswith("Tool"):
            class_name = class_name[:-4]

        import re

        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", class_name)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()
        return name

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the tool with the given parameters.

        Args:
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the result of the tool execution.
        """
        pass

    @abstractmethod
    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates the inputs for the tool.

        Args:
            **kwargs: The arguments to validate.

        Returns:
            A tuple containing a boolean indicating whether the inputs are
            valid and an error message if they are not.
        """
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of the tool."""
        pass

    def get_help(self) -> str:
        """Returns the help text for this tool."""
        help_text = f"Tool: {self.name}\n"
        help_text += f"Description: {self.description}\n\n"
        help_text += "Required inputs:\n"

        schema = self.input_schema
        for field_name, field_def in schema.items():
            required = field_def.get("required", False)
            field_type = field_def.get("type", "any")
            description = field_def.get("description", "No description available")

            status = "REQUIRED" if required else "optional"
            help_text += f"  - {field_name} ({field_type}) [{status}]: {description}\n"

        return help_text

    def _log_execution(self, inputs: dict[str, Any], result: dict[str, Any]) -> None:
        """Logs the execution of the tool."""
        self.execution_count += 1
        self.last_execution_time = time.time()


class ProductSearchTool(ShoppingTool):
    """A tool for searching for products across multiple retailers.

    This tool uses the `UnWrangleCatalogProvider` to search for products based
    on a variety of criteria, including keywords, category, brand, and price.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initializes the ProductSearchTool.

        Args:
            config: The configuration for the tool.
        """
        super().__init__(config)
        try:
            self.provider = UnWrangleCatalogProvider()
        except Exception as e:
            print(f"Warning: Could not initialize UnWrangle provider: {e}")
            self.provider = None

    @property
    def description(self) -> str:
        """Returns a description of the tool."""
        return "Search for products across multiple retailers using various criteria"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        return {
            "query": {
                "type": "string",
                "required": False,
                "description": "Search query/keywords for products",
            },
            "category": {
                "type": "string",
                "required": False,
                "description": "Product category",
            },
            "brands": {
                "type": "array",
                "required": False,
                "description": "List of preferred brands",
            },
            "attributes": {
                "type": "array",
                "required": False,
                "description": "Product attributes/specifications",
            },
            "size": {
                "type": "string",
                "required": False,
                "description": "Product size",
            },
            "color": {
                "type": "string",
                "required": False,
                "description": "Product color preference",
            },
            "budget_min": {
                "type": "number",
                "required": False,
                "description": "Minimum budget/price",
            },
            "budget_max": {
                "type": "number",
                "required": False,
                "description": "Maximum budget/price",
            },
            "products": {
                "type": "array",
                "required": False,
                "description": "Specific product names/models",
            },
        }

    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates that at least one search criterion is provided."""
        required_any = ["query", "brands", "attributes", "products"]

        has_required = False
        for field in required_any:
            value = kwargs.get(field)
            if value and value not in (None, "", [], {}):
                has_required = True
                break

        if not has_required:
            return False, f"At least one of {required_any} must be provided"

        budget_min = kwargs.get("budget_min")
        budget_max = kwargs.get("budget_max")

        if (
            budget_min is not None
            and budget_max is not None
            and budget_min > budget_max
        ):
            return False, "Minimum budget cannot be greater than maximum budget"

        return True, ""

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the product search.

        Args:
            **kwargs: The arguments for the search.

        Returns:
            A dictionary containing the search results.
        """
        if not self.provider:
            return {
                "error": "Product search provider not available",
                "candidates": [],
                "args_used": kwargs,
            }

        try:
            search_items = self._build_search_terms(**kwargs)
            if not search_items:
                return {
                    "error": "No valid search terms provided",
                    "candidates": [],
                    "args_used": kwargs,
                }

            results = self.provider.search_items(
                items=search_items,
                category=kwargs.get("category", "default"),
                **self._build_search_kwargs(**kwargs),
            )

            processed_results = self._process_search_results(results, **kwargs)
            self._log_execution(kwargs, processed_results)
            return processed_results

        except Exception as e:
            error_result = {
                "error": f"Product search failed: {str(e)}",
                "candidates": [],
                "args_used": kwargs,
            }
            self._log_execution(kwargs, error_result)
            return error_result

    def _build_search_terms(self, **kwargs: Any) -> list[str]:
        """Builds a list of search terms from the input arguments."""
        terms = []

        query = kwargs.get("query", "").strip()
        if query:
            terms.extend(query.split())

        for field in ["products", "brands", "attributes"]:
            values = kwargs.get(field, [])
            if values:
                for value in values:
                    if isinstance(value, str) and value.strip():
                        terms.append(value.strip())

        for field in ["size", "color"]:
            if kwargs.get(field):
                terms.append(str(kwargs[field]))

        return list(set(terms))

    def _build_search_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        """Builds additional search parameters for the provider."""
        search_kwargs = {}
        if "timeout" in self.config:
            search_kwargs["timeout"] = self.config["timeout"]
        if "country" in self.config:
            search_kwargs["country"] = self.config["country"]
        return search_kwargs

    def _process_search_results(
        self, results: list[Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Processes the raw provider results into a consistent format."""
        all_candidates = []
        provider_results = {}
        total_found = 0

        for provider_result in results:
            provider_name = provider_result.provider
            products = provider_result.results

            candidates = []
            for product in products:
                candidate = {
                    "id": getattr(product, "product_id", f"demo-{len(candidates)}"),
                    "title": getattr(product, "name", "Unknown Product"),
                    "price": getattr(product, "price", 0),
                    "rating": getattr(product, "rating", 0),
                    "url": getattr(product, "url", ""),
                    "provider": provider_name,
                    "in_stock": getattr(product, "in_stock", True),
                    "brand": getattr(product, "brand", ""),
                }

                if self._matches_budget_criteria(candidate, **kwargs):
                    candidates.append(candidate)

            all_candidates.extend(candidates)
            provider_results[provider_name] = candidates
            total_found += len(candidates)

        filtered_candidates = self._apply_persona_filtering(all_candidates, **kwargs)

        return {
            "candidates": filtered_candidates,
            "total_found": total_found,
            "provider_results": provider_results,
            "args_used": kwargs,
        }

    def _matches_budget_criteria(
        self, candidate: dict[str, Any], **kwargs: Any
    ) -> bool:
        """Checks if a candidate product matches the budget criteria."""
        price = candidate.get("price", 0)
        if not price:
            return True

        budget_min = kwargs.get("budget_min")
        budget_max = kwargs.get("budget_max")

        if budget_min is not None and price < budget_min:
            return False
        if budget_max is not None and price > budget_max:
            return False

        return True

    def _apply_persona_filtering(
        self, candidates: list[dict[str, Any]], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Applies persona-specific filtering and sorting to the results."""
        if not candidates:
            return candidates

        max_results = self.config.get("max_results", 20)
        sort_by = self.config.get("sort_default", "relevance")

        if sort_by == "price_low_to_high":
            candidates.sort(key=lambda x: x.get("price", float("inf")))
        elif sort_by == "price_high_to_low":
            candidates.sort(key=lambda x: x.get("price", 0), reverse=True)
        elif sort_by == "rating_high_to_low":
            candidates.sort(key=lambda x: x.get("rating", 0), reverse=True)

        return candidates[:max_results]


class ProductReviewsTool(ShoppingTool):
    """A tool for getting a review summary for a specific product."""

    @property
    def description(self) -> str:
        """Returns a description of the tool."""
        return "Get review summary and analysis for a specific product"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        return {
            "product": {
                "type": "string",
                "required": True,
                "description": "Product name/identifier",
            }
        }

    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates that a product name is provided."""
        product = kwargs.get("product", "").strip()
        if not product:
            return False, "Product name/identifier is required"
        return True, ""

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the product review analysis.

        Args:
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the review summary.
        """
        product = kwargs.get("product", "").strip()

        # TODO: Integrate with real reviews source
        review_summary = {
            "pros": ["Great picture quality", "Easy to use", "Good value"],
            "cons": ["Setup can be complicated", "Remote is flimsy"],
            "overall_rating": 4.2,
            "total_reviews": 156,
        }

        result = {
            "product": product,
            "review_summary": review_summary,
            "args_used": kwargs,
        }

        self._log_execution(kwargs, result)
        return result


class ProductCompareTool(ShoppingTool):
    """A tool for comparing two or more products side by side."""

    @property
    def description(self) -> str:
        """Returns a description of the tool."""
        return "Compare two or more products side by side"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        return {
            "products": {
                "type": "array",
                "required": True,
                "description": "List of products to compare (minimum 2)",
            }
        }

    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates the inputs for the comparison."""
        products = kwargs.get("products", [])

        if not products or len(products) < 2:
            return False, "At least 2 products are required for comparison"

        if len(products) > 10:
            return False, "Cannot compare more than 10 products at once"

        return True, ""

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the product comparison.

        Args:
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the comparison results.
        """
        products = kwargs.get("products", [])

        # Simple comparison logic (would be enhanced with real data)
        comparison = {
            "winner": products[0] if products else None,
            "items": products.copy(),
        }

        result = {"comparison": comparison, "args_used": kwargs}

        self._log_execution(kwargs, result)
        return result


class AskFollowupsTool(ShoppingTool):
    """A tool for asking clarifying questions."""

    @property
    def description(self) -> str:
        """Returns a description of the tool."""
        return "Ask a clarifying question when missing required information"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        return {
            "question": {
                "type": "string",
                "required": True,
                "description": "The clarifying question to ask",
            }
        }

    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates that a question is provided."""
        question = kwargs.get("question", "").strip()
        if not question:
            return False, "Question text is required"
        return True, ""

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the followup question.

        Args:
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the followup question.
        """
        question = kwargs.get("question", "").strip()

        result = {"question": question, "requires_user_response": True}

        self._log_execution(kwargs, result)
        return result


class CannotAnswerTool(ShoppingTool):
    """A tool for handling requests that cannot be fulfilled."""

    @property
    def description(self) -> str:
        """Returns a description of the tool."""
        return "Handle requests that cannot be completed"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Defines the input schema for this tool."""
        return {
            "reason": {
                "type": "string",
                "required": True,
                "description": "Why the request cannot be completed",
            },
            "user_query": {
                "type": "string",
                "required": True,
                "description": "Original user query",
            },
            "persona_name": {
                "type": "string",
                "required": True,
                "description": "Persona name",
            },
            "route": {
                "type": "string",
                "required": True,
                "description": "Execution route",
            },
        }

    def validate_inputs(self, **kwargs: Any) -> tuple[bool, str]:
        """Validates the required fields for error reporting."""
        required_fields = ["reason", "user_query", "persona_name", "route"]
        for field in required_fields:
            if not kwargs.get(field):
                return False, f"Missing required field: {field}"
        return True, ""

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Executes the cannot-answer response.

        Args:
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the cannot-answer message.
        """
        event_id = audit_event("cannot_answer", kwargs)

        message = (
            f"I can't complete this request right now due to a missing capability. "
            f"I've logged this for the team to address (ref: {event_id}). "
            f"Would you like to try a different approach?"
        )

        result = {
            "message": message,
            "event_id": event_id,
            "reason": kwargs.get("reason"),
        }

        self._log_execution(kwargs, result)
        return result


class ShoppingPersona:
    """A shopping-focused persona with different variants.

    This class encapsulates the behavior of a shopping persona, including its
    configuration, tools, and the logic for parsing user input, planning, and
    executing shopping-related tasks.

    Attributes:
        config (ShoppingConfig): The configuration for the persona.
        _tools (Dict[str, ShoppingTool]): A dictionary of available tools.
        _session_context (Dict[str, Any]): A dictionary to store
            session-specific information.
    """

    def __init__(self, config: ShoppingConfig) -> None:
        """Initializes the ShoppingPersona.

        Args:
            config: The configuration for the persona.
        """
        self.config = config
        self._tools: dict[str, ShoppingTool] = {}
        self._session_context: dict[str, Any] = {}
        self._initialize_tools()

    def _initialize_tools(self) -> None:
        """Initializes the shopping-specific tools for the persona."""
        # Universal tools
        self._tools["ask_followups"] = AskFollowupsTool(
            self.config.tool_configs.get("ask_followups", {})
        )
        self._tools["cannot_answer"] = CannotAnswerTool(
            self.config.tool_configs.get("cannot_answer", {})
        )

        # Shopping-specific tools
        shopping_tools = {
            "product_search": ProductSearchTool,
            "product_reviews": ProductReviewsTool,
            "product_compare": ProductCompareTool,
        }

        for tool_name in self.config.enabled_tools:
            if tool_name in shopping_tools and tool_name not in self._tools:
                tool_config = self.config.tool_configs.get(tool_name, {})
                self._tools[tool_name] = shopping_tools[tool_name](tool_config)

    def parse_user_input(self, user_input: str) -> dict[str, Any]:
        """Parses user input using shopping-specific logic.

        Args:
            user_input: The user's raw input string.

        Returns:
            A dictionary containing the structured attributes extracted from the
            query.
        """
        try:
            resp = completion(
                model=MODEL_PARSER,
                messages=[
                    {"role": "system", "content": self.config.parser_prompt},
                    {"role": "user", "content": user_input},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=600,
                timeout=LITELLM_TIMEOUT,
            )

            parsed = json.loads(resp.choices[0].message.content)

            return {
                "query": parsed.get("query", ""),
                "category": parsed.get("category"),
                "brands": parsed.get("brands", []),
                "attributes": parsed.get("attributes", []),
                "size": parsed.get("size"),
                "color": parsed.get("color"),
                "budget_min": parsed.get("budget_min"),
                "budget_max": parsed.get("budget_max"),
                "products": parsed.get("products", []),
                "confidence": parsed.get("confidence", 0.5),
                "raw_input": user_input,
            }

        except Exception as e:
            return {
                "query": user_input,
                "category": None,
                "brands": [],
                "attributes": [],
                "size": None,
                "color": None,
                "budget_min": None,
                "budget_max": None,
                "products": [],
                "confidence": 0.3,
                "raw_input": user_input,
                "parse_error": str(e),
            }

    def plan_execution(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        """Creates an execution plan using shopping-specific logic.

        Args:
            parsed_input: The structured attributes from the query parser.

        Returns:
            A dictionary containing the execution plan.
        """
        registry_summary = self._build_registry_summary()

        prompt_payload = {
            "registry": registry_summary,
            "attributes": parsed_input,
            "context": {
                "last_selected_product": self._session_context.get(
                    "last_selected_product"
                )
            },
            "constraints": {
                "max_steps": 1,
                "ask_when_missing": True,
                "avoid_fabrication": True,
            },
        }

        try:
            resp = completion(
                model=MODEL_PLANNER,
                messages=[
                    {"role": "system", "content": self.config.planner_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(prompt_payload, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=600,
                timeout=LITELLM_TIMEOUT,
            )

            plan = json.loads(resp.choices[0].message.content)

            plan["steps"] = (plan.get("steps") or [])[:1]
            plan["confidence"] = max(0.0, min(1.0, plan.get("confidence", 0.0)))
            plan["reason"] = str(plan.get("reason", ""))

            return plan

        except Exception as e:
            return {
                "steps": [],
                "confidence": 0.45,
                "clarify": "What product are you interested in?",
                "reason": f"planner error: {e}",
            }

    def execute_tool(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        """Executes a specific tool.

        Args:
            tool_name: The name of the tool to execute.
            **kwargs: The arguments for the tool.

        Returns:
            A dictionary containing the result of the tool execution.
        """
        if tool_name not in self._tools:
            return {"error": f"Tool '{tool_name}' not available"}

        tool = self._tools[tool_name]

        valid, error_msg = tool.validate_inputs(**kwargs)
        if not valid:
            return {"error": f"Invalid inputs for {tool_name}: {error_msg}"}

        try:
            result = tool.execute(**kwargs)
            self._update_session_context(tool_name, kwargs, result)
            return result
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def _build_registry_summary(self) -> dict[str, dict[str, Any]]:
        """Builds a tool registry summary for the planner."""
        registry = {}

        for tool_name, tool in self._tools.items():
            requires = []
            requires_any = []

            schema = tool.input_schema
            for field_name, field_def in schema.items():
                if field_def.get("required", False):
                    requires.append(field_name)

            if tool_name == "product_search":
                requires_any = ["query", "brands", "attributes", "products"]

            registry[tool_name] = {"requires": requires, "requires_any": requires_any}

        return registry

    def _update_session_context(
        self, tool_name: str, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Updates the session context with shopping-specific logic."""
        if tool_name == "product_reviews":
            self._session_context["last_selected_product"] = inputs.get("product")

        if tool_name == "product_compare":
            self._session_context["selection_products"] = inputs.get("products", [])

    @property
    def full_name(self) -> str:
        """Returns the full name of the persona variant."""
        return self.config.full_name

    @property
    def variant(self) -> str:
        """Returns the variant of the persona."""
        return self.config.variant

    def get_available_tools(self) -> dict[str, ShoppingTool]:
        """Returns a copy of the available tools."""
        return self._tools.copy()

    def list_tools(self) -> list[str]:
        """Returns a list of the names of the available tools."""
        return list(self._tools.keys())

    def get_session_context(self) -> dict[str, Any]:
        """Returns a copy of the session context."""
        return self._session_context.copy()

    def clear_session_context(self) -> None:
        """Clears the session context."""
        self._session_context.clear()


class ShoppingPersonaRegistry:
    """A registry for shopping persona variants.

    This class is responsible for loading and managing the different shopping
    persona variants from their configuration files.

    Attributes:
        _loaded_personas (Dict[str, ShoppingPersona]): A cache of loaded
            persona instances.
        _config_cache (Dict[str, ShoppingConfig]): A cache of loaded persona
            configurations.
        _configs_path (Path): The path to the persona configuration files.
    """

    def __init__(self) -> None:
        """Initializes the ShoppingPersonaRegistry."""
        self._loaded_personas: dict[str, ShoppingPersona] = {}
        self._config_cache: dict[str, ShoppingConfig] = {}
        self._configs_path = Path(__file__).parent / "configs" / "shopping_configs"

    def get_persona(self, variant: str = "default") -> ShoppingPersona:
        """Gets or creates a shopping persona instance.

        Args:
            variant: The name of the persona variant to get.

        Returns:
            A `ShoppingPersona` instance.
        """
        if variant not in self._loaded_personas:
            config = self._load_config(variant)
            self._loaded_personas[variant] = ShoppingPersona(config)

        return self._loaded_personas[variant]

    def _load_config(self, variant: str) -> ShoppingConfig:
        """Loads the configuration for a specific persona variant.

        Args:
            variant: The name of the persona variant to load.

        Returns:
            A `ShoppingConfig` object.

        Raises:
            FileNotFoundError: If the configuration file for the specified
                variant is not found.
        """
        if variant not in self._config_cache:
            config_path = self._configs_path / f"{variant}.yaml"

            if not config_path.exists():
                available_variants = (
                    [f.stem for f in self._configs_path.glob("*.yaml")]
                    if self._configs_path.exists()
                    else []
                )
                raise FileNotFoundError(
                    f"Config not found: {config_path}. Available: {available_variants}"
                )

            with open(config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            self._config_cache[variant] = ShoppingConfig(
                name=raw_config["name"],
                variant=raw_config["variant"],
                parser_prompt=raw_config["parser_prompt"],
                planner_prompt=raw_config["planner_prompt"],
                agent_prompt=raw_config["agent_prompt"],
                style=raw_config.get("style", {}),
                policies=raw_config.get("policies", {}),
                capabilities=raw_config.get("capabilities", []),
                enabled_tools=raw_config.get("enabled_tools", []),
                tool_configs=raw_config.get("tool_configs", {}),
                providers=raw_config.get("providers", {}),
            )

        return self._config_cache[variant]

    def list_available_variants(self) -> list[str]:
        """Lists all available shopping persona variants."""
        if not self._configs_path.exists():
            return []
        return [f.stem for f in self._configs_path.glob("*.yaml")]


class ShoppingPersonaRegistry:
    """Registry for shopping persona variants."""

    def __init__(self):
        self._loaded_personas: dict[str, ShoppingPersona] = {}
        self._config_cache: dict[str, ShoppingConfig] = {}
        self._configs_path = Path(__file__).parent / "configs" / "shopping_configs"

    def get_persona(self, variant: str = "default") -> ShoppingPersona:
        """Get or create a shopping persona instance."""
        if variant not in self._loaded_personas:
            config = self._load_config(variant)
            self._loaded_personas[variant] = ShoppingPersona(config)

        return self._loaded_personas[variant]

    def _load_config(self, variant: str) -> ShoppingConfig:
        """Load configuration for a specific variant."""
        if variant not in self._config_cache:
            config_path = self._configs_path / f"{variant}.yaml"

            if not config_path.exists():
                available_variants = (
                    [f.stem for f in self._configs_path.glob("*.yaml")]
                    if self._configs_path.exists()
                    else []
                )
                raise FileNotFoundError(
                    f"Config not found: {config_path}. Available: {available_variants}"
                )

            with open(config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            self._config_cache[variant] = ShoppingConfig(
                name=raw_config["name"],
                variant=raw_config["variant"],
                parser_prompt=raw_config["parser_prompt"],
                planner_prompt=raw_config["planner_prompt"],
                agent_prompt=raw_config["agent_prompt"],
                style=raw_config.get("style", {}),
                policies=raw_config.get("policies", {}),
                capabilities=raw_config.get("capabilities", []),
                enabled_tools=raw_config.get("enabled_tools", []),
                tool_configs=raw_config.get("tool_configs", {}),
                providers=raw_config.get("providers", {}),
            )

        return self._config_cache[variant]

    def list_available_variants(self) -> list[str]:
        """List all available shopping persona variants."""
        if not self._configs_path.exists():
            return []
        return [f.stem for f in self._configs_path.glob("*.yaml")]
