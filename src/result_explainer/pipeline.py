"""Question -> SQL -> facts -> explainer -> validator, with one retry and a safe fallback.

Statuses:
    grounded  the explainer's text passed every grounding check
    template  the deterministic template was asked for directly
    fallback  the explainer failed or was rejected; the template text is shown instead
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from result_explainer.explainers.base import Explainer, ExplainerError
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import FactTable, build_facts
from result_explainer.paths import DEFAULT_DB
from result_explainer.questions import Question, run_question
from result_explainer.validator import CITATION, validate

MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class Attempt:
    text: str | None   # None when the explainer raised instead of answering
    issues: list[str]  # validation messages, or the explainer error


@dataclass(frozen=True)
class Explanation:
    facts: FactTable
    text: str
    status: str
    explainer: str  # who wrote `text`
    attempts: list[Attempt]

    @property
    def question(self) -> Question:
        return self.facts.question

    def cited_refs(self) -> list[str]:
        return list(dict.fromkeys(CITATION.findall(self.text)))


def explain_question(
    question: Question, explainer: Explainer, db_path: Path = DEFAULT_DB
) -> Explanation:
    facts = build_facts(question, run_question(question, db_path))
    return explain_facts(facts, explainer)


def explain_facts(
    facts: FactTable, explainer: Explainer, max_attempts: int = MAX_ATTEMPTS
) -> Explanation:
    template = TemplateExplainer()
    if isinstance(explainer, TemplateExplainer):
        return Explanation(facts, template.explain(facts), "template", template.name, [])

    attempts: list[Attempt] = []
    feedback: list[str] | None = None
    for _ in range(max_attempts):
        try:
            text = explainer.explain(facts, feedback)
        except ExplainerError as error:
            # Configuration and network problems don't fix themselves on a retry.
            attempts.append(Attempt(None, [f"explainer_error: {error}"]))
            break
        result = validate(text, facts)
        attempts.append(Attempt(text, result.messages()))
        if result.ok:
            return Explanation(facts, text, "grounded", explainer.name, attempts)
        feedback = result.messages()

    return Explanation(facts, template.explain(facts), "fallback", template.name, attempts)
