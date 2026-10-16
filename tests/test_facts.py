from decimal import Decimal

import pytest

from result_explainer.facts import ROW_COUNT_REF, build_facts
from result_explainer.formatting import format_value, round_half_up
from result_explainer.questions import QueryResult, load_questions

QUESTIONS = load_questions()
Q05 = QUESTIONS["q05"]
Q05_RESULT = QueryResult(
    columns=list(Q05.columns),
    rows=[("2025-01", 85657.45, None, None), ("2025-02", 67727.13, 85657.45, -20.9)],
)


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (85657.45, "currency", "$85,657.45"),
        (1234, "count", "1,234"),
        (-20.9, "percent", "-20.9%"),
        (7.45, "number", "7.5"),
        (0.0, "percent", "0.0%"),
        (None, "currency", "n/a"),
        ("2025-03", "label", "2025-03"),
    ],
)
def test_format_value(value, kind, expected):
    assert format_value(value, kind) == expected


def test_rounding_is_half_up_not_bankers():
    assert round_half_up(2.5, 0) == Decimal("3")
    assert round_half_up(0.125, 2) == Decimal("0.13")


def test_every_cell_gets_a_reference():
    facts = build_facts(Q05, Q05_RESULT)
    expected = {f"r{row}.{column}" for row in (1, 2) for column in Q05.columns}
    assert set(facts.facts) == expected | {ROW_COUNT_REF}


def test_fact_keeps_display_value_and_row():
    fact = build_facts(Q05, Q05_RESULT).facts["r2.growth_pct"]
    assert (fact.display, fact.value, fact.row) == ("-20.9%", Decimal("-20.9"), 2)


def test_null_cell_displays_na_and_cannot_back_a_number():
    fact = build_facts(Q05, Q05_RESULT).facts["r1.growth_pct"]
    assert fact.display == "n/a"
    assert fact.value is None


def test_row_count_is_a_citable_fact():
    fact = build_facts(Q05, Q05_RESULT).facts[ROW_COUNT_REF]
    assert (fact.display, fact.value) == ("2", Decimal(2))


def test_row_label_joins_label_columns():
    q02 = QUESTIONS["q02"]
    result = QueryResult(list(q02.columns), [(1, "HD Webcam", "Electronics", 255, 116099.04)])
    assert build_facts(q02, result).row_label(1) == "HD Webcam / Electronics"


def test_empty_result_only_has_the_row_count():
    facts = build_facts(Q05, QueryResult(list(Q05.columns), []))
    assert facts.is_empty
    assert list(facts.facts) == [ROW_COUNT_REF]


def test_integer_labels_can_back_numbers_but_text_labels_cannot():
    q10 = QUESTIONS["q10"]
    facts = build_facts(q10, QueryResult(list(q10.columns), [(123, "North", "2025-05-01", 15)]))
    assert facts.facts["r1.order_id"].value == Decimal(123)
    assert facts.facts["r1.region"].value is None
    assert facts.facts["r1.order_date"].value is None
