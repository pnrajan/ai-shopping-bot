"""Shopping Tool Registry for Inflection Curator.

This module provides functions for building a tool registry from shopping tools
and validating tool arguments against the registry. The registry is a summary of
the available tools and their requirements, which is used by the planner to
generate valid execution plans.

Example:
    >>> from inflection_curator.planning import build_registry_from_shopping_tools, validate_args
    >>> tools = {"product_search": ProductSearchTool()}
    >>> registry = build_registry_from_shopping_tools(tools)
    >>> is_valid, error = validate_args(registry, "product_search", {"query": "laptop"})
    >>> print(is_valid)
    True
"""

from typing import Dict, Any, List
from ..personas.shopping import ShoppingTool


def build_registry_from_shopping_tools(
    tools: dict[str, ShoppingTool], extra_requires_any: dict[str, list[str]] = None
) -> dict[str, dict[str, Any]]:
    """Builds a registry from shopping tools for the planner.

    Args:
        tools: A dictionary of tool names to ShoppingTool instances.
        extra_requires_any: A dictionary of additional "requires_any"
            constraints.

    Returns:
        A registry dictionary with tool requirements.
    """
    spec: dict[str, dict[str, Any]] = {}

    for tool_name, tool in tools.items():
        requires = []
        schema = tool.input_schema

        # Extract required fields from schema
        for field_name, field_def in schema.items():
            if field_def.get("required", False):
                requires.append(field_name)

        spec[tool_name] = {"requires": requires, "requires_any": []}

    # Add extra requires_any constraints
    if extra_requires_any:
        for tool_name, fields in extra_requires_any.items():
            if tool_name in spec:
                spec[tool_name]["requires_any"] = fields

    return spec


def validate_args(
    registry: dict[str, dict[str, Any]], tool: str, args: dict[str, Any]
) -> tuple[bool, str]:
    """Validates tool arguments against registry requirements.

    Args:
        registry: The tool registry with requirements.
        tool: The name of the tool to validate.
        args: The arguments to validate.

    Returns:
        A tuple containing a boolean indicating whether the arguments are
        valid and an error message if they are not.
    """
    if tool not in registry:
        return False, f"Unknown tool: {tool}"

    r = registry[tool]

    # Check required fields
    for req in r["requires"]:
        if args.get(req) in (None, "", [], {}):
            return False, f"Missing required arg '{req}' for {tool}"

    # Check requires_any (at least one must be present)
    if r["requires_any"]:
        if not any(args.get(k) not in (None, "", [], {}) for k in r["requires_any"]):
            return False, f"{tool} requires one of {r['requires_any']}"

    return True, ""
