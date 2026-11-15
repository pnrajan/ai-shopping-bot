"""Execution plan and its result."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    tool: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    why: str = ""


class ExecutionPlan(BaseModel):
    route: str
    steps: list[ExecutionStep] = Field(default_factory=list)
    needs_clarification: bool = False
    questions: list[str] = Field(default_factory=list)
    source: str = Field("pattern", description="pattern | llm")


class StepResult(BaseModel):
    tool: str
    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: int = 0


class ExecutionResponse(BaseModel):
    success: bool
    results: list[StepResult] = Field(default_factory=list)
    error: str | None = None

    def result_for(self, tool: str) -> StepResult | None:
        return next((r for r in self.results if r.tool == tool and r.success), None)
