"""Pipeline stages. Each has one ``run(ctx)`` and knows nothing about the others."""

from shopper.stages.base import Stage
from shopper.stages.compare import CompareStage
from shopper.stages.enrich import EnrichStage
from shopper.stages.execute import ExecuteStage
from shopper.stages.persist import PersistStage
from shopper.stages.plan import PlanStage
from shopper.stages.refine import RefineStage
from shopper.stages.respond import RespondStage
from shopper.stages.understand import UnderstandStage

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
