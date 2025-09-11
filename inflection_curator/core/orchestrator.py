"""Shopping Orchestrator for Inflection Curator.

This module defines the main orchestrator for the shopping assistant. It manages
the overall workflow, including persona management, query parsing, planning, and
execution. The orchestrator is the primary entry point for handling user requests.

Example:
    >>> from inflection_curator.core import ShoppingOrchestrator
    >>> orchestrator = ShoppingOrchestrator()
    >>> result = orchestrator.handle("I'm looking for a new laptop")
    >>> print(result)
"""

import json
from typing import Dict, Any, Optional, List
from ..personas.shopping import ShoppingPersonaRegistry, ShoppingPersona
from ..planning.query_parser import ShoppingQueryParser
from ..planning.planner import ShoppingPlanner
from ..planning.executor import ShoppingExecutor
from ..planning.registry import build_registry_from_shopping_tools, validate_args
from ..classifiers.query_understanding import QueryUnderstanding, QueryAnalysisResult
from ..utils.config import MODEL_PARSER


class ShoppingMode:
    """Defines the execution modes for the ShoppingOrchestrator."""

    DIRECT_TOOL = "direct_tool"  # Execute single best tool directly
    PLANNED_EXECUTION = "planned_execution"  # AI-planned execution with validation

    # Legacy compatibility
    LLM_ONLY = "llm_only"  # Same as planned_execution
    AGENT_ONLY = "agent_only"  # Same as direct_tool
    LLM_THEN_AGENT_FALLBACK = "fallback"  # Planned with direct fallback


class ShoppingOrchestrator:
    """Orchestrates the shopping assistant's workflow."""

    def __init__(self) -> None:
        """Initializes the ShoppingOrchestrator."""
        self.persona_registry = ShoppingPersonaRegistry()
        self.current_persona: ShoppingPersona | None = None
        self.execution_mode = ShoppingMode.PLANNED_EXECUTION
        self.session_context: dict[str, Any] = {}

        # Initialize the planning pipeline components
        self.parser = QueryUnderstanding()

        # These will be initialized after setting persona
        self.registry = None
        self.planner = None
        self.executor = None

        # Set default persona
        self.set_persona("default")

        # Legacy compatibility mapping
        self._mode_mapping = {
            ShoppingMode.LLM_ONLY: ShoppingMode.PLANNED_EXECUTION,
            ShoppingMode.AGENT_ONLY: ShoppingMode.DIRECT_TOOL,
        }

    def set_persona(self, variant: str = "default") -> None:
        """Sets the active shopping persona."""
        try:
            self.current_persona = self.persona_registry.get_persona(variant)
            self.session_context.clear()  # Clear context when switching personas

            # Initialize planning components with persona's tools
            tools = self.current_persona.get_available_tools()
            self.registry = build_registry_from_shopping_tools(
                tools,
                extra_requires_any={
                    "product_search": ["query", "brands", "attributes", "products"]
                },
            )

            self.planner = ShoppingPlanner(self.registry)
            self.executor = ShoppingExecutor(tools)

        except Exception as e:
            available = self.persona_registry.list_available_variants()
            raise ValueError(
                f"Failed to set persona '{variant}': {e}. Available: {available}"
            )

    def set_mode(self, mode: str) -> None:
        """Sets the execution mode."""
        # Handle legacy mode names
        if mode in self._mode_mapping:
            mode = self._mode_mapping[mode]

        valid_modes = [
            ShoppingMode.DIRECT_TOOL,
            ShoppingMode.PLANNED_EXECUTION,
            ShoppingMode.LLM_ONLY,
            ShoppingMode.AGENT_ONLY,
            ShoppingMode.LLM_THEN_AGENT_FALLBACK,
        ]

        if mode not in valid_modes:
            raise ValueError(
                f"Invalid execution mode: {mode}. Valid modes: {valid_modes}"
            )

        self.execution_mode = mode

    def handle(self, user_input: str, **context: Any) -> dict[str, Any]:
        """Handles a user's shopping request."""
        if not self.current_persona:
            return {"error": "No shopping persona available"}

        try:
            # Update session context
            self.session_context.update(context)

            # Step 1: Parse user query into structured attributes
            query_analysis_result = self.parser.analyze_query(user_input)
            if query_analysis_result:
                attrs = query_analysis_result.to_dict()
            else:
                # Handle the case where query analysis fails
                attrs = {}  # Or some default value

            # Route to appropriate execution mode
            if self.execution_mode in [
                ShoppingMode.DIRECT_TOOL,
                ShoppingMode.AGENT_ONLY,
            ]:
                return self._execute_direct_tool(user_input, attrs)

            elif self.execution_mode in [
                ShoppingMode.PLANNED_EXECUTION,
                ShoppingMode.LLM_ONLY,
            ]:
                return self._execute_planned(user_input, attrs)

            elif self.execution_mode == ShoppingMode.LLM_THEN_AGENT_FALLBACK:
                return self._execute_with_fallback(user_input, attrs)

            else:
                return {"error": f"Unknown execution mode: {self.execution_mode}"}

        except Exception as e:
            return {
                "error": f"Request processing failed: {str(e)}",
                "user_input": user_input,
                "persona": (
                    self.current_persona.full_name
                    if self.current_persona
                    else "unknown"
                ),
                "execution_mode": self.execution_mode,
            }

    def _execute_direct_tool(
        self, user_input: str, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        """Executes a tool directly without a planning step."""
        best_tool = self._select_best_tool(attrs)

        if not best_tool:
            return self._handle_no_tool_available(user_input, attrs)

        tool_name, tool_args = best_tool

        # Execute using the executor for consistency
        plan = {"steps": [{"tool": tool_name, "args": tool_args}]}
        exec_result = self.executor.run(plan, self.session_context)

        return {
            "route": (
                "agent_only"
                if self.execution_mode == ShoppingMode.AGENT_ONLY
                else "direct_tool"
            ),
            "persona": self.current_persona.full_name,
            "attributes": attrs,
            "execution": exec_result,
            "context": self.session_context,
        }

    def _execute_planned(
        self, user_input: str, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        """Executes a tool based on an AI-generated plan."""
        # Step 2: Generate plan from attributes
        plan = self.planner.build(attrs, self.session_context, self.current_persona)

        # Check if plan requires clarification
        if not plan.get("steps"):
            return {
                "route": self.execution_mode,
                "persona": self.current_persona.full_name,
                "attributes": attrs,
                "plan": plan,
                "execution": {
                    "tool": None,
                    "args": None,
                    "output": None,
                    "clarify": plan.get("clarify"),
                },
                "context": self.session_context,
            }

        # Step 3: Validate the planned step against registry
        step = plan["steps"][0]
        tool_name = step["tool"]
        tool_args = step.get("args", {})

        is_valid, validation_error = validate_args(self.registry, tool_name, tool_args)
        tool_available = tool_name in self.executor.tools

        if not is_valid or not tool_available:
            # Handle validation failure - use cannot_answer tool
            if not tool_available:
                fallback_reason = "tool_not_available"
            else:
                fallback_reason = f"validation_error: {validation_error}"

            fallback = self.executor.tools["cannot_answer"].execute(
                reason=fallback_reason,
                user_query=user_input,
                parsed_attrs=attrs,
                planned_tool=tool_name,
                planned_args=tool_args,
                persona_name=self.current_persona.full_name,
                route=self.execution_mode,
            )

            return {
                "route": self.execution_mode,
                "persona": self.current_persona.full_name,
                "attributes": attrs,
                "plan": plan,
                "execution": {"tool": "cannot_answer", "output": fallback},
                "context": self.session_context,
            }

        # Step 4: Execute the validated plan
        exec_result = self.executor.run(plan, self.session_context)

        return {
            "route": self.execution_mode,
            "persona": self.current_persona.full_name,
            "attributes": attrs,
            "plan": plan,
            "execution": exec_result,
            "context": self.session_context,
        }

    def _execute_with_fallback(
        self, user_input: str, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        """Executes with LLM planning and falls back to direct execution."""
        # Try planned execution first
        planned_result = self._execute_planned(user_input, attrs)

        # Check if planning failed or needs fallback
        execution = planned_result.get("execution", {})

        if execution.get("tool") == "cannot_answer" or execution.get("tool") is None:

            # Fall back to direct tool execution (agent route)
            fallback_result = self._execute_direct_tool(user_input, attrs)

            return {
                "route": "llm_then_agent_fallback",
                "reason": "planning_failed_fallback_to_agent",
                "persona": self.current_persona.full_name,
                "attributes": attrs,
                "final": fallback_result.get("execution", {}).get("output"),
                "context": self.session_context,
            }

        return planned_result

    def _select_best_tool(
        self, attrs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Selects the best tool for direct execution based on parsed attributes."""
        # Tool selection logic based on parsed attributes
        if attrs.get("products") and len(attrs["products"]) >= 2:
            if "product_compare" in self.executor.tools:
                return "product_compare", {"products": attrs["products"]}

        if attrs.get("products") and len(attrs["products"]) == 1:
            if "product_reviews" in self.executor.tools:
                return "product_reviews", {"product": attrs["products"][0]}

        if attrs.get("query") or attrs.get("brands") or attrs.get("attributes"):
            if "product_search" in self.executor.tools:
                search_args = {
                    k: v
                    for k, v in attrs.items()
                    if k
                    in [
                        "query",
                        "category",
                        "brands",
                        "attributes",
                        "size",
                        "color",
                        "budget_min",
                        "budget_max",
                    ]
                    and v
                }
                return "product_search", search_args

        # If no clear tool match, ask for followup
        if "ask_followups" in self.executor.tools:
            return "ask_followups", {
                "question": "Could you provide more details about what you're looking for?"
            }

        return None

    def _handle_no_tool_available(
        self, user_input: str, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        """Handles cases where no appropriate tool can be found."""
        if "cannot_answer" in self.executor.tools:
            result = self.executor.tools["cannot_answer"].execute(
                reason="no_suitable_tool_found",
                user_query=user_input,
                parsed_attrs=attrs,
                persona_name=self.current_persona.full_name,
                route=self.execution_mode,
            )

            return {
                "route": "error_handling",
                "persona": self.current_persona.full_name,
                "attributes": attrs,
                "execution": {"tool": "cannot_answer", "output": result},
            }
        else:
            return {
                "route": "error_handling",
                "persona": self.current_persona.full_name,
                "attributes": attrs,
                "error": "No suitable tool found and no error handler available",
                "available_tools": list(self.executor.tools.keys()),
            }

    # Convenience methods
    def list_personas(self) -> list[str]:
        """Lists all available shopping persona variants."""
        return self.persona_registry.list_available_variants()

    def get_current_persona_info(self) -> dict[str, Any]:
        """Gets information about the current persona."""
        if not self.current_persona:
            return {"error": "No persona selected"}

        return {
            "variant": self.current_persona.variant,
            "full_name": self.current_persona.full_name,
            "available_tools": self.current_persona.list_tools(),
            "execution_mode": self.execution_mode,
        }

    def get_session_context(self) -> dict[str, Any]:
        """Gets the current session context."""
        context = {
            "orchestrator_context": self.session_context.copy(),
            "execution_mode": self.execution_mode,
        }

        if self.current_persona:
            context["persona_context"] = self.current_persona.get_session_context()
            context["persona"] = self.current_persona.full_name

        return context

    def clear_session_context(self) -> None:
        """Clears all session context."""
        self.session_context.clear()
        if self.current_persona:
            self.current_persona.clear_session_context()

    # Legacy compatibility properties and methods
    @property
    def mode(self) -> str:
        """Legacy property for execution mode."""
        return self.execution_mode

    @mode.setter
    def mode(self, value: str) -> None:
        """Legacy setter for execution mode."""
        self.set_mode(value)

    def set_persona_legacy(self, name: str) -> None:
        """Legacy persona setting method."""
        # Map legacy names
        if name in ["default", "concise"]:
            self.set_persona(name)
        else:
            self.set_persona(name)  # Try as-is

    # For compatibility with existing main.py
    @property
    def personas(self) -> "MockPersonaRegistry":
        """Legacy personas property."""

        class MockPersonaRegistry:
            def get(self, name):
                class MockPersona:
                    def __init__(self, variant):
                        self.name = variant

                return MockPersona(name)

        return MockPersonaRegistry()
