"""Plain-text rendering of results and explanations for the terminal (ASCII only)."""

from __future__ import annotations

import textwrap

from result_explainer.facts import FactTable
from result_explainer.pipeline import Explanation

WIDTH = 88


def render_table(facts: FactTable) -> str:
    if facts.is_empty:
        return "(no rows)"
    header = facts.columns
    rows = [[fact.display for fact in facts.row(n)] for n in range(1, facts.row_count + 1)]
    widths = [max(len(name), *(len(row[i]) for row in rows)) for i, name in enumerate(header)]
    numeric = [facts.question.columns[name] != "label" for name in header]

    def line(cells: list[str]) -> str:
        padded = (
            cell.rjust(width) if is_number else cell.ljust(width)
            for cell, width, is_number in zip(cells, widths, numeric)
        )
        return "  ".join(padded).rstrip()

    return "\n".join([line(header), line(["-" * width for width in widths])] + [line(row) for row in rows])


STATUS_LINES = {
    "grounded": "grounded - written by {explainer}, every number checked against the result",
    "template": "template - deterministic summary, no model used",
    "fallback": "fallback - the model's answer was rejected, showing the template summary instead",
    "empty": "empty result - nothing to explain, the model was not called",
}


def render_explanation(explanation: Explanation, show_sql: bool = False, show_facts: bool = False) -> str:
    question = explanation.question
    facts = explanation.facts
    parts = [f"{question.id} | {question.title}", question.question, ""]
    if show_sql:
        parts += ["SQL", textwrap.indent(question.sql.strip(), "  "), ""]
    parts += [render_table(facts), ""]
    if show_facts:
        parts += ["Facts"] + [f"  [{fact.ref}] = {fact.display}" for fact in facts.facts.values()] + [""]

    status = STATUS_LINES[explanation.status].format(explainer=explanation.explainer)
    parts += [f"Explanation ({status})", _wrap(explanation.text), ""]

    rejected = [attempt for attempt in explanation.attempts if attempt.issues]
    if rejected:
        parts.append("Rejected attempts")
        for number, attempt in enumerate(rejected, start=1):
            shown = attempt.text if attempt.text is not None else "(no answer)"
            parts.append(_wrap(f"{number}. [{attempt.explainer}] {shown}", indent="  ", subsequent="     "))
            parts += [
                _wrap(f"- {issue.kind}: {issue.detail}", indent="     ", subsequent="       ")
                for issue in attempt.issues
            ]
        parts.append("")

    cited = explanation.cited_refs()
    if cited:
        parts.append("Cited facts")
        width = max(len(ref) for ref in cited) + 2
        for ref in cited:
            fact = facts.facts[ref]
            label = facts.row_label(fact.row) if fact.row else "rows returned"
            parts.append(f"  {f'[{ref}]':<{width}}  {fact.display:>14}  {label}".rstrip())
    return "\n".join(parts).rstrip()


def _wrap(text: str, indent: str = "", subsequent: str | None = None) -> str:
    return textwrap.fill(
        text, width=WIDTH, initial_indent=indent,
        subsequent_indent=indent if subsequent is None else subsequent,
    )
