"""Build the object graph from settings. Nothing here runs at import time."""

from __future__ import annotations

from dataclasses import dataclass

from shopper.cache.semantic import InMemoryBackend, SemanticCache
from shopper.llm.client import LLMClient, OpenAICompatibleClient
from shopper.llm.fake import FakeLLM
from shopper.pipeline import ShoppingPipeline
from shopper.providers.base import CatalogProvider
from shopper.providers.fake import FakeProvider
from shopper.providers.unwrangle import UnWrangleProvider
from shopper.search.handler import SearchHandler
from shopper.session.store import InMemorySessionStore, SessionStore, SQLiteSessionStore
from shopper.settings import Settings
from shopper.stages import (
    CompareStage,
    EnrichStage,
    ExecuteStage,
    PersistStage,
    PlanStage,
    RefineStage,
    RespondStage,
    UnderstandStage,
)
from shopper.tools import get_registry


@dataclass
class Services:
    settings: Settings
    llm: LLMClient
    provider: CatalogProvider
    search: SearchHandler
    store: SessionStore
    cache: SemanticCache
    pipeline: ShoppingPipeline


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


def build_services(
    settings: Settings,
    *,
    llm: LLMClient | None = None,
    provider: CatalogProvider | None = None,
    store: SessionStore | None = None,
) -> Services:
    llm = llm or build_llm(settings)
    provider = provider or build_provider(settings)
    store = store or build_store(settings)
    cache = SemanticCache(InMemoryBackend(settings.cache_max_size), ttl_s=settings.cache_ttl_s)
    search = SearchHandler(
        provider,
        cache=cache,
        timeout_s=settings.search_timeout_s,
        default_limit=settings.search_limit,
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
    return Services(settings, llm, provider, search, store, cache, pipeline)
