"""Runtime configuration. The only module allowed to name models or read API keys.

Model ids use the form ``provider/model``. Supported providers: ``openai``, ``siliconflow``,
``openrouter``. Each resolves to an OpenAI-compatible endpoint with its own key and base URL.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelRole(StrEnum):
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    RESPONSE = "response"
    ENRICH = "enrich"


class ModelSettings(BaseModel):
    understanding: str = "openai/gpt-4o-mini"
    planning: str = "openai/gpt-4o-mini"
    response: str = "openai/gpt-4o-mini"
    enrich: str = "openai/gpt-4o-mini"

    def for_role(self, role: ModelRole) -> str:
        return getattr(self, role.value)


class ProviderEndpoint(BaseModel):
    base_url: str
    key_env: str
    json_mode: bool = True


PROVIDER_ENDPOINTS: dict[str, ProviderEndpoint] = {
    "openai": ProviderEndpoint(base_url="https://api.openai.com/v1", key_env="OPENAI_API_KEY"),
    "siliconflow": ProviderEndpoint(
        base_url="https://api.siliconflow.com/v1", key_env="SILICONFLOW_API_KEY"
    ),
    "openrouter": ProviderEndpoint(
        base_url="https://openrouter.ai/api/v1", key_env="OPENROUTER_API_KEY", json_mode=False
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHOPPER_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    llm: str = Field("fake", description="fake | live")
    models: ModelSettings = Field(default_factory=ModelSettings)
    llm_max_calls_per_request: int = 4
    llm_timeout_s: float = 30.0

    catalog: str = Field("fake", description="fake | unwrangle")
    unwrangle_api_key: SecretStr | None = Field(None, validation_alias="UNWRANGLE_APIKEY")
    search_timeout_s: float = 8.0
    search_limit: int = 10

    openai_api_key: SecretStr | None = Field(None, validation_alias="OPENAI_API_KEY")
    siliconflow_api_key: SecretStr | None = Field(None, validation_alias="SILICONFLOW_API_KEY")
    siliconflow_base_url: str | None = Field(None, validation_alias="SILICONFLOW_BASE_URL")
    openrouter_api_key: SecretStr | None = Field(None, validation_alias="OPENROUTER_API_KEY")

    session_store: Literal["memory", "sqlite"] = "memory"
    sqlite_path: str = "shopper.db"
    cache_ttl_s: int = 24 * 60 * 60
    cache_max_size: int = 1000

    api_key: SecretStr | None = Field(
        None, description="Clients send it as X-API-Key. Unset: open."
    )
    rate_limit_per_minute: int = 60

    otel_endpoint: str | None = Field(None, description="OTLP HTTP endpoint for stage spans")

    enrich_comparison: bool = True
    enrich_essentials: bool = True
    enrich_rationale: bool = True

    def provider_key(self, provider: str) -> str | None:
        secret = {
            "openai": self.openai_api_key,
            "siliconflow": self.siliconflow_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(provider)
        return secret.get_secret_value() if secret else None

    def provider_base_url(self, provider: str) -> str:
        if provider == "siliconflow" and self.siliconflow_base_url:
            return self.siliconflow_base_url
        return PROVIDER_ENDPOINTS[provider].base_url


def get_settings() -> Settings:
    return Settings()
