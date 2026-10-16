"""A deliberately unreliable explainer, used only to demonstrate the grounding guard.

It behaves like a careless model: it cites a real fact but inflates its value by 25% and
adds a comparison the query never computed. It ignores feedback, so the pipeline always
rejects it and falls back to the template. Only used with ``--explainer faulty``.
"""

from __future__ import annotations

from decimal import Decimal

from result_explainer.facts import FactTable
from result_explainer.formatting import format_value


class FaultyExplainer:
    name = "faulty"

    def explain(self, facts: FactTable, feedback: list[str] | None = None) -> str:
        focus = [
            f for f in facts.facts.values()
            if f.column == facts.question.focus and f.value is not None
        ]
        if not focus:
            return "There were 3 problem orders, mostly in the Central region."
        fact = max(focus, key=lambda f: f.value)
        inflated = format_value(fact.value * Decimal("1.25"), fact.kind)
        where = facts.row_label(fact.row) or "The top result"
        return f"{where} led with {inflated} [{fact.ref}], roughly double the next best result."
