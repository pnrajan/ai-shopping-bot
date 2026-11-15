"""Build the object graph from settings. Nothing here runs at import time."""

from __future__ import annotations

from dataclasses import dataclass

from ai_shopping_bot.api.tracing import TraceSink, build_sink
from ai_shopping_bot.cache.semantic import InMemoryBackend, SemanticCache
from ai_shopping_bot.llm.client import LLMClient, OpenAICompatibleClient
from ai_shopping_bot.llm.fake import FakeLLM
from ai_shopping_bot.pipeline import ShoppingPipeline
from ai_shopping_bot.providers.base import CatalogProvider
from ai_shopping_bot.providers.fake import FakeProvider
from ai_shopping_bot.providers.unwrangle import UnWrangleProvider
from ai_shopping_bot.search.handler import SearchHandler
from ai_shopping_bot.session.store import InMemorySessionStore, SessionStore, SQLiteSessionStore
from ai_shopping_bot.settings import Settings
from ai_shopping_bot.stages import (
    CompareStage,
    EnrichStage,
    ExecuteStage,
    PersistStage,
    PlanStage,
    RefineStage,
    RespondStage,
    UnderstandStage,
)
from ai_shopping_bot.tools import get_registry
from ai_shopping_bot.tracking import (
    AvailabilityMonitor,
    AvailabilityStore,
    InMemoryAvailabilityStore,
    SQLiteAvailabilityStore,
)


@dataclass
class Services:
    settings: Settings
    llm: LLMClient
    provider: CatalogProvider
    search: SearchHandler
    store: SessionStore
    cache: SemanticCache
    pipeline: ShoppingPipeline
    tracer: TraceSink
    tracker: AvailabilityStore | None
    monitor: AvailabilityMonitor | None


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm == "fake":
        return FakeLLM()
    return OpenAICompatibleClient(settings)


def build_provider(settings: Settings) -> CatalogProvider:
    if settings.catalog == "unwrangle":
        key = settings.unwrangle_api_key.get_secret_value() if settings.unwrangle_api_key else ""
        return UnWrangleProvider(key)
    return FakeProvider()


def build_store(settings: Settings) -> SessionStore:
    if settings.session_store == "sqlite":
        return SQLiteSessionStore(settings.sqlite_path)
    return InMemorySessionStore()


def build_tracker(settings: Settings) -> AvailabilityStore | None:
    if settings.tracking == "off":
        return None
    if settings.tracking == "sqlite":
        return SQLiteAvailabilityStore(settings.tracking_sqlite_path or settings.sqlite_path)
    return InMemoryAvailabilityStore()


def build_services(
    settings: Settings,
    *,
    llm: LLMClient | None = None,
    provider: CatalogProvider | None = None,
    store: SessionStore | None = None,
    tracker: AvailabilityStore | None = None,
) -> Services:
    llm = llm or build_llm(settings)
    provider = provider or build_provider(settings)
    store = store or build_store(settings)
    tracker = tracker or build_tracker(settings)
    monitor = (
        AvailabilityMonitor(
            tracker,
            {provider.name: provider},
            interval_s=settings.tracking_monitor_interval_s,
            timeout_s=settings.search_timeout_s,
        )
        if tracker
        else None
    )
    cache = SemanticCache(InMemoryBackend(settings.cache_max_size), ttl_s=settings.cache_ttl_s)
    search = SearchHandler(
        provider,
        cache=cache,
        timeout_s=settings.search_timeout_s,
        default_limit=settings.search_limit,
        tracker=tracker,
    )
    stages = [
        UnderstandStage(llm),
        RefineStage(llm),
        CompareStage(search),
        PlanStage(llm),
        ExecuteStage(get_registry(), search, llm),
        RespondStage(llm),
        EnrichStage(llm, settings),
    ]
    pipeline = ShoppingPipeline(
        stages,
        final=PersistStage(store),
        store=store,
        max_llm_calls=settings.llm_max_calls_per_request,
    )
    return Services(
        settings,
        llm,
        provider,
        search,
        store,
        cache,
        pipeline,
        build_sink(settings.otel_endpoint),
        tracker,
        monitor,
    )
