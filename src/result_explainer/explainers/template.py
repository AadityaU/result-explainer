"""Deterministic explainer: no model, always grounded. Used offline and as the fallback."""

from __future__ import annotations

from result_explainer.facts import ROW_COUNT_REF, Fact, FactTable


def humanize(column: str) -> str:
    """'avg_order_value' -> 'average order value', 'repeat_rate_pct' -> 'repeat rate'."""
    words = column.removesuffix("_pct").split("_")
    return " ".join("average" if word == "avg" else word for word in words)


class TemplateExplainer:
    name = "template"

    def explain(self, facts: FactTable, feedback: list[str] | None = None) -> str:
        count = facts.facts[ROW_COUNT_REF]
        noun = "row" if facts.row_count == 1 else "rows"
        opening = f"The query returned {count.display} {noun} [{ROW_COUNT_REF}]"
        if facts.is_empty:
            return f'{opening}, so nothing matched the question "{facts.question.title}".'
        if facts.row_count == 1:
            return " ".join([f"{opening}."] + [_metric_sentence(f) for f in _metrics(facts.row(1))])

        focus = [f for f in facts.facts.values() if f.column == facts.question.focus and f.value is not None]
        if not focus:
            return f"{opening}, but none of them has a {humanize(facts.question.focus)} value."
        top = max(focus, key=lambda f: f.value)
        bottom = min(focus, key=lambda f: f.value)
        metric = humanize(top.column)

        sentences = [f"{opening}."]
        sentences.append(
            f"{metric.capitalize()} peaked at {top.display} for {_where(facts, top)} [{top.ref}]."
        )
        others = [f for f in _metrics(facts.row(top.row)) if f.column != top.column]
        if others:
            listed = ", ".join(f"{humanize(f.column)} {f.display} [{f.ref}]" for f in others)
            sentences.append(f"That row also shows {listed}.")
        if bottom.ref != top.ref:
            sentences.append(
                f"The lowest {metric} was {bottom.display} for {_where(facts, bottom)} [{bottom.ref}]."
            )
        return " ".join(sentences)


def _metrics(row: list[Fact]) -> list[Fact]:
    return [fact for fact in row if fact.kind != "label" and fact.value is not None]


def _metric_sentence(fact: Fact) -> str:
    return f"{humanize(fact.column).capitalize()}: {fact.display} [{fact.ref}]."


def _where(facts: FactTable, fact: Fact) -> str:
    return facts.row_label(fact.row) or f"row {fact.row}"
