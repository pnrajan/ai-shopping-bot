"""Single entry point for model calls, with per-request budget and structured output.

Providers are OpenAI-compatible endpoints selected by the ``provider/`` prefix of the model id:

- ``openai/<model>``        api.openai.com
- ``siliconflow/<model>``   api.siliconflow.com, ``enable_thinking`` off for hybrid models
- ``openrouter/<model>``    openrouter.ai, ``reasoning`` off; retried if the model refuses
"""

from __future__ import annotations

import time
from typing import Any, Protocol, TypeVar

from openai import APIError, OpenAI
from pydantic import BaseModel, ValidationError

from shopper.contracts.context import LLMBudget
from shopper.logging import get_logger, log_event
from shopper.settings import PROVIDER_ENDPOINTS, ModelRole, Settings

T = TypeVar("T", bound=BaseModel)
log = get_logger("llm")


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete(
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        budget: LLMBudget,
        purpose: str,
        schema: type[T] | None = None,
        max_tokens: int = 800,
    ) -> T | str: ...


def split_model(model_id: str) -> tuple[str, str]:
    provider, _, model = model_id.partition("/")
    if provider not in PROVIDER_ENDPOINTS or not model:
        raise LLMError(f"model id must be provider/model with a known provider, got {model_id!r}")
    return provider, model


def _extra_body(provider: str, reasoning_off: bool) -> dict[str, Any]:
    if not reasoning_off:
        return {}
    if provider == "siliconflow":
        return {"enable_thinking": False}
    if provider == "openrouter":
        return {"reasoning": {"enabled": False}}
    return {}


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._clients: dict[str, OpenAI] = {}
        self._must_reason: set[str] = set()

    def _client(self, provider: str) -> OpenAI:
        if provider not in self._clients:
            key = self._settings.provider_key(provider)
            if not key:
                raise LLMError(f"{PROVIDER_ENDPOINTS[provider].key_env} is not set")
            self._clients[provider] = OpenAI(
                api_key=key,
                base_url=self._settings.provider_base_url(provider),
                timeout=self._settings.llm_timeout_s,
                max_retries=2,
            )
        return self._clients[provider]

    def complete(
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        budget: LLMBudget,
        purpose: str,
        schema: type[T] | None = None,
        max_tokens: int = 800,
    ) -> T | str:
        budget.consume(purpose)
        model_id = self._settings.models.for_role(role)
        provider, model = split_model(model_id)
        json_mode = schema is not None and PROVIDER_ENDPOINTS[provider].json_mode
        if schema is not None:
            system = (
                f"{system}\n\nRespond with JSON only, matching this schema:\n"
                f"{schema.model_json_schema()}"
            )
        text = self._send(provider, model, system, user, max_tokens, json_mode, purpose)
        if schema is None:
            return text
        try:
            return schema.model_validate_json(_strip_fences(text))
        except ValidationError as first:
            repair = (
                f"{user}\n\nYour previous answer failed validation: "
                f"{first.errors()[:3]}. Return corrected JSON."
            )
            text = self._send(
                provider, model, system, repair, max_tokens, json_mode, purpose + ".repair"
            )
            try:
                return schema.model_validate_json(_strip_fences(text))
            except ValidationError as second:
                raise LLMError(f"{purpose}: model output did not match schema") from second

    def _send(
        self,
        provider: str,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        json_mode: bool,
        purpose: str,
    ) -> str:
        key = f"{provider}/{model}"
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "extra_body": _extra_body(provider, key not in self._must_reason),
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        try:
            try:
                completion = self._client(provider).chat.completions.create(**kwargs)
            except APIError as e:
                if "reasoning is mandatory" not in str(e).lower():
                    raise
                self._must_reason.add(key)
                kwargs["extra_body"] = {}
                completion = self._client(provider).chat.completions.create(**kwargs)
        except APIError as e:
            raise LLMError(f"{purpose}: {provider} call failed: {e.__class__.__name__}") from e
        usage = completion.usage
        log_event(
            log,
            "llm.call",
            purpose=purpose,
            model=key,
            ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise LLMError(f"{purpose}: empty completion from {key}")
        return content


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    return text.strip()
