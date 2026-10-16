import json

import httpx
import pytest

from result_explainer.explainers.base import ExplainerError
from result_explainer.explainers.llm import (
    DEFAULT_BASE_URL,
    DRAFT_MODEL,
    RETRY_MODEL,
    SYSTEM_PROMPT,
    LLMExplainer,
    LLMSettings,
    build_messages,
    llm_configured,
    routed_explainers,
)
from result_explainer.facts import build_facts
from result_explainer.questions import QueryResult, load_questions

Q06 = load_questions()["q06"]
FACTS = build_facts(Q06, QueryResult(list(Q06.columns), [(1722, 956, 55.5)]))
SETTINGS = LLMSettings(api_key="sk-test", base_url="http://llm.test/v1")


def explainer_returning(response, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return response(request) if callable(response) else response
    return LLMExplainer(SETTINGS, "test-model", httpx.Client(transport=httpx.MockTransport(handler)))


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
    settings = LLMSettings(base_url="http://localhost:11434/v1")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: seen.append(r) or chat_response("ok")))
    LLMExplainer(settings, "llama", client).explain(FACTS)
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


def test_a_slow_answer_hits_the_total_deadline():
    settings = LLMSettings(api_key="sk-test", base_url="http://llm.test/v1", timeout_seconds=0)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: chat_response("late")))
    with pytest.raises(ExplainerError, match="did not answer within 0s"):
        LLMExplainer(settings, "slow-model", client).explain(FACTS)


def test_unreachable_endpoint_raises_explainer_error():
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)
    with pytest.raises(ExplainerError, match="Could not reach"):
        explainer_returning(refuse).explain(FACTS)


def test_only_the_api_key_is_required():
    settings = LLMSettings.from_env({"LLM_API_KEY": "sk-secret"})
    assert (settings.base_url, settings.draft_model, settings.retry_model) == (
        DEFAULT_BASE_URL, DRAFT_MODEL, RETRY_MODEL,
    )
    assert "sk-secret" not in repr(settings)


def test_overrides_allow_a_local_server_without_a_key():
    settings = LLMSettings.from_env({
        "LLM_BASE_URL": "http://localhost:11434/v1",
        "LLM_DRAFT_MODEL": "llama",
        "LLM_RETRY_MODEL": "qwen",
        "LLM_TIMEOUT_SECONDS": "15",
    })
    assert (settings.api_key, settings.draft_model, settings.retry_model, settings.timeout_seconds) == (
        None, "llama", "qwen", 15.0,
    )


def test_openrouter_without_a_key_is_a_clear_error():
    with pytest.raises(ExplainerError, match="LLM_API_KEY"):
        LLMSettings.from_env({})


def test_settings_reject_a_bad_timeout():
    with pytest.raises(ExplainerError, match="LLM_TIMEOUT_SECONDS"):
        LLMSettings.from_env({"LLM_API_KEY": "k", "LLM_TIMEOUT_SECONDS": "soon"})


def test_routing_drafts_with_one_model_and_retries_with_the_other():
    draft, retry = routed_explainers(SETTINGS)
    assert (draft.name, retry.name) == (f"llm ({DRAFT_MODEL})", f"llm ({RETRY_MODEL})")
    assert draft._client is retry._client


def test_routing_with_one_model_reuses_it_for_the_retry():
    draft, retry = routed_explainers(LLMSettings(api_key="k", draft_model="m", retry_model="m"))
    assert draft is retry


def test_llm_is_used_when_a_key_or_endpoint_is_configured():
    assert llm_configured({"LLM_API_KEY": "k"})
    assert llm_configured({"LLM_BASE_URL": "http://localhost:11434/v1"})
    assert not llm_configured({})
