import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from ai_shopping_bot.contracts.context import LLMBudget
from ai_shopping_bot.llm.client import (
    LLMError,
    OpenAICompatibleClient,
    _extra_body,
    _strip_fences,
    split_model,
)
from ai_shopping_bot.settings import ModelRole, Settings


class Out(BaseModel):
    answer: str
    score: float


def _settings(**models):
    return Settings(
        _env_file=None,
        llm="live",
        models=models,
        openai_api_key="k-openai",
        siliconflow_api_key="k-sf",
        openrouter_api_key="k-or",
    )


def _completion(content):
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def test_split_model_requires_known_provider():
    assert split_model("siliconflow/Qwen/Qwen3-8B") == ("siliconflow", "Qwen/Qwen3-8B")
    with pytest.raises(LLMError):
        split_model("gpt-4o-mini")


def test_extra_body_per_provider():
    assert _extra_body("siliconflow", True) == {"enable_thinking": False}
    assert _extra_body("openrouter", True) == {"reasoning": {"enabled": False}}
    assert _extra_body("openai", True) == {}
    assert _extra_body("openrouter", False) == {}


def test_strip_fences():
    assert _strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_fences('{"a": 1}') == '{"a": 1}'


@respx.mock
def test_siliconflow_route_and_schema_parse():
    route = respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_completion('{"answer": "hi", "score": 0.9}'))
    )
    c = OpenAICompatibleClient(_settings(understanding="siliconflow/Qwen/Qwen3-8B"))
    b = LLMBudget(max_calls=2)
    out = c.complete(
        role=ModelRole.UNDERSTANDING, system="s", user="u", budget=b, purpose="t", schema=Out
    )
    assert out == Out(answer="hi", score=0.9)
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "Qwen/Qwen3-8B"
    assert body["enable_thinking"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert route.calls[0].request.headers["authorization"] == "Bearer k-sf"
    assert b.used == 1


@respx.mock
def test_openrouter_retries_when_reasoning_mandatory():
    url = "https://openrouter.ai/api/v1/chat/completions"
    route = respx.post(url).mock(
        side_effect=[
            httpx.Response(
                400, json={"error": {"message": "Reasoning is mandatory for this model"}}
            ),
            httpx.Response(200, json=_completion("fine")),
        ]
    )
    c = OpenAICompatibleClient(_settings(response="openrouter/anthropic/claude-sonnet-5-5"))
    out = c.complete(
        role=ModelRole.RESPONSE, system="s", user="u", budget=LLMBudget(5), purpose="t"
    )
    assert out == "fine"
    first = json.loads(route.calls[0].request.content)
    second = json.loads(route.calls[1].request.content)
    assert first["reasoning"] == {"enabled": False}
    assert "reasoning" not in second
    assert "response_format" not in first


@respx.mock
def test_schema_repair_then_error():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_completion("not json"))
    )
    c = OpenAICompatibleClient(_settings())
    with pytest.raises(LLMError):
        c.complete(
            role=ModelRole.PLANNING,
            system="s",
            user="u",
            budget=LLMBudget(5),
            purpose="t",
            schema=Out,
        )


def test_missing_key_is_clear_error():
    s = Settings(_env_file=None, llm="live", models={"response": "openrouter/x/y"})
    c = OpenAICompatibleClient(s)
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        c.complete(role=ModelRole.RESPONSE, system="s", user="u", budget=LLMBudget(5), purpose="t")
