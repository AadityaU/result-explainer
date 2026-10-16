"""The only module that talks to a language model: any OpenAI-compatible chat endpoint.

Models are chosen automatically. The draft model answers first. A model from a different family
is only called when that draft fails the grounding checks (it gets the validator's feedback), or
when the draft model errors or misses the deadline.

The assignment comes from ``python -m result_explainer evaluate`` (docs/model-evaluation.md).
gemini-4-argon and glm-5.3 were both grounded on every question, almost always on the first
attempt. Gemini never took more than 14s, while glm-5.3 sometimes took minutes, so glm-5.3 is
the cheap second opinion rather than the first answer. glm-5.3-flash was slower than both.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from result_explainer.explainers.base import ExplainerError
from result_explainer.facts import FactTable

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DRAFT_MODEL = "google/gemini-4-argon"
RETRY_MODEL = "z-ai/glm-5.3"

SYSTEM_PROMPT = """\
You explain SQL query results to business readers in plain language.

Rules:
1. Use only the facts provided. Never invent, estimate or calculate a number: no sums,
   differences, ratios, averages, percentages or rankings that are not already a fact.
2. Every sentence that contains a number must cite the fact it came from, using the
   fact id in square brackets right after the number, for example [r2.net_revenue].
3. Copy numbers exactly as they are displayed in the facts.
4. When a sentence names a row (a month, region, product, category or channel), cite a
   fact from that same row in that sentence.
5. A fact shown as n/a has no value. Say it is not available; never replace it with a number.
6. Do not use words like doubled, tripled, twice or "x times". Use higher, lower,
   largest or smallest instead.
7. Write 3 to 5 short sentences of plain prose. No headings, lists or tables.
8. If the facts cannot answer part of the question, say so instead of guessing."""


def build_messages(facts: FactTable, feedback: list[str] | None = None) -> list[dict[str, str]]:
    """The chat messages for one attempt; feedback carries a rejected draft's issues."""
    question = facts.question
    lines = [
        f"Question: {question.title}",
        f"What it asks: {question.question}",
        "",
        "Facts:",
    ]
    for fact in facts.facts.values():
        label = facts.row_label(fact.row) if fact.row and fact.kind != "label" else ""
        context = f" ({label})" if label else ""
        lines.append(f"[{fact.ref}] {fact.column} = {fact.display}{context}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]
    if feedback:
        problems = "\n".join(f"- {message}" for message in feedback)
        messages.append({
            "role": "user",
            "content": f"A draft answer failed these checks:\n{problems}\n"
                       "Write a new answer that follows every rule.",
        })
    return messages


@dataclass(frozen=True)
class LLMSettings:
    api_key: str | None = field(default=None, repr=False)  # never printed
    base_url: str = DEFAULT_BASE_URL
    draft_model: str = DRAFT_MODEL
    retry_model: str = RETRY_MODEL
    timeout_seconds: float = 45.0  # per answer, start to finish

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LLMSettings:
        """Only LLM_API_KEY is needed for OpenRouter.

        LLM_BASE_URL, LLM_DRAFT_MODEL, LLM_RETRY_MODEL and LLM_TIMEOUT_SECONDS are optional
        overrides, e.g. for a local Ollama server, which needs no key.
        """
        env = os.environ if env is None else env

        def setting(name: str, default: str) -> str:
            return env.get(name, "").strip() or default

        api_key = env.get("LLM_API_KEY", "").strip() or None
        base_url = setting("LLM_BASE_URL", DEFAULT_BASE_URL)
        if api_key is None and base_url == DEFAULT_BASE_URL:
            raise ExplainerError(
                "LLM_API_KEY is not set. Copy .env.example to .env and add your OpenRouter key."
            )
        timeout = env.get("LLM_TIMEOUT_SECONDS", "").strip()
        try:
            timeout_seconds = float(timeout) if timeout else cls.timeout_seconds
        except ValueError:
            raise ExplainerError(f"LLM_TIMEOUT_SECONDS must be a number, got {timeout!r}") from None
        return cls(
            api_key,
            base_url,
            setting("LLM_DRAFT_MODEL", DRAFT_MODEL),
            setting("LLM_RETRY_MODEL", RETRY_MODEL),
            timeout_seconds,
        )


def llm_configured(env: Mapping[str, str] | None = None) -> bool:
    """True when a key or a custom endpoint is set, so explanations should use the model."""
    env = os.environ if env is None else env
    return bool(env.get("LLM_API_KEY", "").strip() or env.get("LLM_BASE_URL", "").strip())


class LLMExplainer:
    def __init__(self, settings: LLMSettings, model: str, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.model = model
        self.name = f"llm ({model})"
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)

    def explain(self, facts: FactTable, feedback: list[str] | None = None) -> str:
        headers = {}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        payload = {
            "model": self.model,
            "messages": build_messages(facts, feedback),
            "temperature": 0,
        }
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        # httpx's timeout only limits the gap between bytes, and OpenRouter keeps a slow request
        # alive with filler bytes, so the whole answer gets its own deadline.
        deadline = time.monotonic() + self.settings.timeout_seconds
        try:
            with self._client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise ExplainerError(
                            f"{self.model} did not answer within {self.settings.timeout_seconds:g}s"
                        )
                    body.extend(chunk)
            content = json.loads(body)["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as error:
            raise ExplainerError(
                f"LLM endpoint returned HTTP {error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise ExplainerError(f"Could not reach the LLM endpoint at {url}: {error}") from error
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ExplainerError("LLM endpoint returned an unexpected response") from error
        if not isinstance(content, str) or not content.strip():
            raise ExplainerError("LLM endpoint returned an empty answer")
        return content.strip()


def routed_explainers(settings: LLMSettings, client: httpx.Client | None = None) -> list[LLMExplainer]:
    """[draft, retry]: the draft model answers; the retry model only handles failed drafts."""
    client = client or httpx.Client(timeout=settings.timeout_seconds)
    draft = LLMExplainer(settings, settings.draft_model, client)
    if settings.retry_model == settings.draft_model:
        return [draft, draft]
    return [draft, LLMExplainer(settings, settings.retry_model, client)]
