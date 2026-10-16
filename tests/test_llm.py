import json

import httpx
import pytest

from result_explainer.explainers.base import ExplainerError
from result_explainer.explainers.llm import (
    SYSTEM_PROMPT,
    LLMExplainer,
    LLMSettings,
    build_messages,
    configured_models,
)
from result_explainer.facts import build_facts
from result_explainer.questions import QueryResult, load_questions

Q06 = load_questions()["q06"]
FACTS = build_facts(Q06, QueryResult(list(Q06.columns), [(1722, 956, 55.5)]))
SETTINGS = LLMSettings("http://llm.test/v1", "test-model", api_key="sk-test")


def explainer_returning(response, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return response(request) if callable(response) else response
    return LLMExplainer(SETTINGS, httpx.Client(transport=httpx.MockTransport(handler)))


def chat_response(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_sends_facts_to_the_chat_completions_endpoint():
    seen = []
    text = explainer_returning(chat_response(" Rate was 55.5% [r1.repeat_rate_pct]. "), seen).explain(FACTS)

    assert text == "Rate was 55.5% [r1.repeat_rate_pct]."
    request = seen[0]
    assert str(request.url) == "http://llm.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-test"
    payload = json.loads(request.content)
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0
    assert payload["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "[r1.repeat_rate_pct] repeat_rate_pct = 55.5%" in payload["messages"][1]["content"]


def test_no_auth_header_without_a_key():
    seen = []
    settings = LLMSettings("http://localhost:11434/v1", "llama")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: seen.append(r) or chat_response("ok")))
    LLMExplainer(settings, client).explain(FACTS)
    assert "Authorization" not in seen[0].headers


def test_feedback_is_sent_as_a_follow_up_message():
    messages = build_messages(FACTS, ["invented_number: 60% does not appear anywhere in the result"])
    assert len(messages) == 3
    assert "60% does not appear" in messages[2]["content"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, text="not json"),
        chat_response("   "),
    ],
    ids=["http-error", "wrong-shape", "not-json", "empty-answer"],
)
def test_bad_responses_raise_explainer_error(response):
    with pytest.raises(ExplainerError):
        explainer_returning(response).explain(FACTS)


def test_unreachable_endpoint_raises_explainer_error():
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)
    with pytest.raises(ExplainerError, match="Could not reach"):
        explainer_returning(refuse).explain(FACTS)


def test_settings_from_env():
    settings = LLMSettings.from_env({
        "LLM_BASE_URL": "https://api.example.com/v1",
        "LLM_MODEL": "some-model",
        "LLM_API_KEY": "sk-secret",
        "LLM_TIMEOUT_SECONDS": "15",
    })
    assert (settings.base_url, settings.model, settings.timeout_seconds) == (
        "https://api.example.com/v1", "some-model", 15.0,
    )
    assert "sk-secret" not in repr(settings)


def test_model_can_be_overridden_per_request():
    settings = SETTINGS.with_model("google/gemini-4-argon")
    assert (settings.model, settings.api_key) == ("google/gemini-4-argon", "sk-test")
    assert SETTINGS.with_model(None) is SETTINGS
    assert LLMExplainer(settings).name == "llm (google/gemini-4-argon)"


def test_configured_models_lists_the_default_first():
    env = {"LLM_MODEL": "a/one", "LLM_MODELS": "b/two, a/one ,c/three"}
    assert configured_models(env) == ["b/two", "a/one", "c/three"]
    assert configured_models({"LLM_MODEL": "a/one", "LLM_MODELS": "b/two"}) == ["a/one", "b/two"]
    assert configured_models({}) == []


def test_settings_require_url_and_model():
    with pytest.raises(ExplainerError, match="LLM_BASE_URL and LLM_MODEL"):
        LLMSettings.from_env({"LLM_API_KEY": "sk-secret"})


def test_settings_reject_a_bad_timeout():
    with pytest.raises(ExplainerError, match="LLM_TIMEOUT_SECONDS"):
        LLMSettings.from_env({"LLM_BASE_URL": "http://x", "LLM_MODEL": "m", "LLM_TIMEOUT_SECONDS": "soon"})
