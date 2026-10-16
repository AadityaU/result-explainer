"""The interface every explainer implements. Only ``explainers/llm.py`` calls a model."""

from __future__ import annotations

from typing import Protocol

from result_explainer.facts import FactTable


class ExplainerError(RuntimeError):
    """The explainer produced no text: missing configuration, network error or bad response."""


class Explainer(Protocol):
    name: str

    def explain(self, facts: FactTable, feedback: list[str] | None = None) -> str:
        """Explain the facts in plain language, citing each number as ``[ref]``.

        ``feedback`` lists what the validator rejected in the previous attempt, if any.
        """
        ...
