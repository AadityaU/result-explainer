"""Turn query rows into referenced facts: the only values an explanation may use.

Every cell becomes a fact with a reference id ``r{row}.{column}`` (rows start at 1),
plus ``meta.row_count``. Explanations cite facts in square brackets: ``[r3.net_revenue]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from result_explainer.formatting import format_value, numeric_value
from result_explainer.questions import QueryResult, Question

ROW_COUNT_REF = "meta.row_count"


@dataclass(frozen=True)
class Fact:
    ref: str
    column: str
    kind: str
    display: str
    value: Decimal | None  # numeric value as displayed; None for NULLs and text labels
    row: int | None        # 1-based row number; None for meta facts


@dataclass(frozen=True)
class FactTable:
    question: Question
    columns: list[str]
    row_count: int
    facts: dict[str, Fact]  # by reference id, meta first, then row by row

    @property
    def is_empty(self) -> bool:
        return self.row_count == 0

    def row(self, number: int) -> list[Fact]:
        return [self.facts[f"r{number}.{column}"] for column in self.columns]

    def row_label(self, number: int) -> str:
        """The row's label values, e.g. 'HD Webcam / Electronics'. Empty if it has none."""
        return " / ".join(fact.display for fact in self.row(number) if fact.kind == "label")

    def labels(self) -> set[str]:
        return {fact.display for fact in self.facts.values() if fact.kind == "label"}


def build_facts(question: Question, result: QueryResult) -> FactTable:
    row_count = len(result.rows)
    facts = {
        ROW_COUNT_REF: Fact(
            ROW_COUNT_REF, "row_count", "count", format_value(row_count, "count"),
            Decimal(row_count), None,
        )
    }
    for number, row in enumerate(result.rows, start=1):
        for column, value in zip(result.columns, row):
            kind = question.columns[column]
            ref = f"r{number}.{column}"
            facts[ref] = Fact(
                ref, column, kind, format_value(value, kind), numeric_value(value, kind), number
            )
    return FactTable(question, list(result.columns), row_count, facts)
