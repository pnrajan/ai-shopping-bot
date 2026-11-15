from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shopper.api.app import create_app
from shopper.api.wiring import Services, build_services
from shopper.llm.fake import FakeLLM
from shopper.providers.fake import FakeProvider
from shopper.session.store import InMemorySessionStore
from shopper.settings import Settings


class CountingProvider(FakeProvider):
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query, *, category=None, limit=10, timeout_s=8.0):
        self.calls += 1
        return super().search(query, category=category, limit=limit, timeout_s=timeout_s)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, llm="fake", catalog="fake", session_store="memory")


@pytest.fixture
def services(settings) -> Services:
    return build_services(
        settings, llm=FakeLLM(), provider=CountingProvider(), store=InMemorySessionStore()
    )


@pytest.fixture
def client(settings, services):
    app = create_app(settings, services)
    with TestClient(app) as c:
        yield c
