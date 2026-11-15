"""Tool registry. Tools receive their collaborators (search handler, LLM) through ``ToolDeps``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ai_shopping_bot.contracts.context import LLMBudget
from ai_shopping_bot.contracts.tools import ToolInput, ToolOutput

if TYPE_CHECKING:
    from ai_shopping_bot.llm.client import LLMClient
    from ai_shopping_bot.search.handler import SearchHandler


@dataclass
class ToolDeps:
    search: SearchHandler
    llm: LLMClient
    budget: LLMBudget


ToolFn = Callable[[ToolInput, ToolDeps], ToolOutput]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fn: ToolFn


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> dict[str, Any]:
        return {n: s.description for n, s in self._tools.items()}


_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry


def tool(name: str, description: str) -> Callable[[ToolFn], ToolFn]:
    def deco(fn: ToolFn) -> ToolFn:
        _registry.register(ToolSpec(name=name, description=description, fn=fn))
        return fn

    return deco
