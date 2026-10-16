"""Question -> SQL -> facts -> explainer -> validator, with one retry and a safe fallback.

An answer gets one attempt from each explainer in the list it is given, in order. With a
language model configured the list is [draft model, retry model]: the retry model is only
called, with the validator's feedback, when the draft is rejected or the draft model fails
(see ``explainers/llm.py``).

Statuses:
    empty     the query returned no rows; no explainer is called
    grounded  an explainer's text passed every grounding check
    template  the deterministic template was asked for directly
    fallback  every attempt failed or was rejected; the template text is shown instead
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from result_explainer.explainers.base import Explainer, ExplainerError
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import FactTable, build_facts
from result_explainer.paths import DEFAULT_DB
from result_explainer.questions import Question, run_question
from result_explainer.validator import Issue, citations, validate

MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class Attempt:
    explainer: str       # who wrote this attempt
    text: str | None     # None when the explainer raised instead of answering
    issues: list[Issue]  # validation issues, or the explainer error


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
        return list(dict.fromkeys(citations(self.text)))


def with_retry(explainer: Explainer) -> list[Explainer]:
    """The same explainer for every attempt."""
    return [explainer] * MAX_ATTEMPTS


def explain_question(
    question: Question, explainers: Sequence[Explainer], db_path: Path = DEFAULT_DB
) -> Explanation:
    facts = build_facts(question, run_question(question, db_path))
    return explain_facts(facts, explainers)


def explain_facts(facts: FactTable, explainers: Sequence[Explainer]) -> Explanation:
    template = TemplateExplainer()
    if facts.is_empty:
        # Nothing to explain: a model given no data can only make something up.
        return Explanation(facts, template.explain(facts), "empty", template.name, [])
    if isinstance(explainers[0], TemplateExplainer):
        return Explanation(facts, template.explain(facts), "template", template.name, [])

    attempts: list[Attempt] = []
    feedback: list[str] | None = None
    for position, explainer in enumerate(explainers):
        try:
            text = explainer.explain(facts, feedback)
        except ExplainerError as error:
            attempts.append(Attempt(explainer.name, None, [Issue("explainer_error", str(error))]))
            if all(later is explainer for later in explainers[position + 1:]):
                break  # asking the same explainer again won't fix a network or config error
            continue
        result = validate(text, facts)
        attempts.append(Attempt(explainer.name, text, result.issues))
        if result.ok:
            return Explanation(facts, text, "grounded", explainer.name, attempts)
        feedback = result.messages()

    return Explanation(facts, template.explain(facts), "fallback", template.name, attempts)
