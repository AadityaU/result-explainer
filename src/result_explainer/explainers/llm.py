"""The only module that talks to a language model: any OpenAI-compatible chat endpoint."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from result_explainer.explainers.base import ExplainerError
from result_explainer.facts import FactTable

SYSTEM_PROMPT = """\
You explain SQL query results to business readers in plain language.

Rules:
1. Use only the facts provided. Never invent, estimate or calculate a number: no sums,
   differences, ratios, averages, percentages or rankings that are not already a fact.
2. Every sentence that contains a number must cite the fact it came from, using the
   fact id in square brackets right after the number, for example [r2.net_revenue].
3. Copy numbers exactly as they are displayed in the facts.
4. A fact shown as n/a has no value. Say it is not available; never replace it with a number.
5. Do not use words like doubled, tripled, twice or "x times". Use higher, lower,
   largest or smallest instead.
6. Write 3 to 5 short sentences of plain prose. No headings, lists or tables.
7. If the facts cannot answer part of the question, say so instead of guessing."""


def build_messages(facts: FactTable, feedback: list[str] | None = None) -> list[dict[str, str]]:
    """The chat messages for one attempt; feedback carries the previous attempt's issues."""
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
            "content": f"Your previous answer failed these checks:\n{problems}\n"
                       "Write a new answer that follows every rule.",
        })
    return messages


@dataclass(frozen=True)
class LLMSettings:
    base_url: str  # e.g. http://localhost:11434/v1 for Ollama
    model: str
    api_key: str | None = field(default=None, repr=False)  # never printed
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LLMSettings:
        """Read LLM_BASE_URL, LLM_MODEL, LLM_API_KEY and LLM_TIMEOUT_SECONDS.

        The key is optional because local servers such as Ollama don't need one.
        """
        env = os.environ if env is None else env
        base_url = env.get("LLM_BASE_URL", "").strip()
        model = env.get("LLM_MODEL", "").strip()
        if not base_url or not model:
            raise ExplainerError(
                "LLM_BASE_URL and LLM_MODEL must be set to use the LLM explainer "
                "(copy .env.example to .env and fill it in)."
            )
        timeout = env.get("LLM_TIMEOUT_SECONDS", "").strip()
        try:
            timeout_seconds = float(timeout) if timeout else 60.0
        except ValueError:
            raise ExplainerError(f"LLM_TIMEOUT_SECONDS must be a number, got {timeout!r}") from None
        return cls(base_url, model, env.get("LLM_API_KEY", "").strip() or None, timeout_seconds)


class LLMExplainer:
    name = "llm"

    def __init__(self, settings: LLMSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)

    def explain(self, facts: FactTable, feedback: list[str] | None = None) -> str:
        headers = {}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        payload = {
            "model": self.settings.model,
            "messages": build_messages(facts, feedback),
            "temperature": 0,
        }
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        try:
            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
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
