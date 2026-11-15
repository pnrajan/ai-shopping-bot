"""Pipeline stages. Each has one ``run(ctx)`` and knows nothing about the others."""

from ai_shopping_bot.stages.base import Stage
from ai_shopping_bot.stages.compare import CompareStage
from ai_shopping_bot.stages.enrich import EnrichStage
from ai_shopping_bot.stages.execute import ExecuteStage
from ai_shopping_bot.stages.persist import PersistStage
from ai_shopping_bot.stages.plan import PlanStage
from ai_shopping_bot.stages.refine import RefineStage
from ai_shopping_bot.stages.respond import RespondStage
from ai_shopping_bot.stages.understand import UnderstandStage

__all__ = [
    "CompareStage",
    "EnrichStage",
    "ExecuteStage",
    "PersistStage",
    "PlanStage",
    "RefineStage",
    "RespondStage",
    "Stage",
    "UnderstandStage",
]
