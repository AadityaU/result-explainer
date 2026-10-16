import pytest

from result_explainer.facts import build_facts
from result_explainer.questions import QueryResult, load_questions
from result_explainer.validator import validate

QUESTIONS = load_questions()


def facts_for(question_id, rows):
    question = QUESTIONS[question_id]
    return build_facts(question, QueryResult(list(question.columns), rows))


MONTHLY = facts_for(
    "q01",
    [("2025-01", 263, 87181.29), ("2025-02", 248, 80656.39), ("2025-12", 529, 170979.87)],
)
GROWTH = facts_for(
    "q05",
    [("2025-01", 87181.29, None, None), ("2025-02", 80656.39, 87181.29, -7.5)],
)


def kinds(text, facts=MONTHLY):
    return [issue.kind for issue in validate(text, facts).issues]


def test_accepts_a_fully_grounded_explanation():
    text = (
        "Net revenue peaked in 2025-12 at $170,979.87 [r3.net_revenue] from 529 delivered "
        "orders [r3.delivered_orders]. February was the quietest month at $80,656.39 "
        "[r2.net_revenue]."
    )
    assert kinds(text) == []


@pytest.mark.parametrize("written", ["$87,181.29", "$87,181", "$87.2k", "87.18k", "$0.1M"])
def test_accepts_rounded_and_abbreviated_values(written):
    assert kinds(f"January brought in {written} [r1.net_revenue].") == []


def test_rejects_an_invented_number():
    assert kinds("December reached $200,000.00 [r3.net_revenue].") == ["invented_number"]


def test_rejects_truncation_that_is_not_rounding():
    # $170,979.87 rounds to $171k, so "$170k" is not a faithful rounding.
    assert kinds("December reached $170k [r3.net_revenue].") == ["invented_number"]


def test_rejects_a_number_backed_by_the_wrong_citation():
    assert kinds("December reached $170,979.87 [r1.net_revenue].") == ["uncited_number"]


def test_every_sentence_with_a_number_needs_its_own_citation():
    text = "January had 263 orders [r1.delivered_orders]. December had 529 orders."
    assert kinds(text) == ["uncited_number"]


def test_rejects_unknown_references():
    assert kinds("Revenue was strong [r9.net_revenue] [r1.net_revenue].") == ["unknown_reference"]


def test_requires_at_least_one_citation():
    assert kinds("Revenue grew through the year.") == ["no_citations"]


def test_rejects_an_empty_explanation():
    assert kinds("   ") == ["empty"]


def test_label_digits_and_question_numbers_need_no_citation():
    # "2025-02" is a label; "2025" appears in the question text.
    text = "In 2025, the month 2025-02 had the fewest orders at 248 [r2.delivered_orders]."
    assert kinds(text) == []


def test_question_numbers_are_allowed_for_rankings():
    top = facts_for("q02", [(1, "HD Webcam", "Electronics", 255, 116099.04)])
    assert kinds("Among the top 10, HD Webcam led with $116,099.04 [r1.net_revenue].", top) == []


def test_negative_values_can_be_described_in_words():
    assert kinds("Revenue fell 7.5% in February [r2.growth_pct].", GROWTH) == []


def test_null_values_cannot_back_a_number():
    assert kinds("January growth was 0% [r1.growth_pct].", GROWTH) == ["invented_number"]


@pytest.mark.parametrize(
    "text",
    [
        "December revenue nearly doubled [r3.net_revenue].",
        "December earned 2x January [r3.net_revenue].",
        "December was two times as strong [r3.net_revenue].",
    ],
)
def test_flags_wording_that_implies_extra_calculation(text):
    assert "unsupported_calculation" in kinds(text)


def test_empty_result_can_only_report_that_nothing_was_returned():
    empty = facts_for("q10", [])
    assert kinds("The query returned 0 rows [meta.row_count].", empty) == []
    assert kinds("Only 3 orders were late.", empty) == ["invented_number"]


def test_integer_labels_must_be_cited_like_numbers():
    late = facts_for("q10", [(4242, "Central", "2025-05-01", 15)])
    assert kinds("Order 4242 [r1.order_id] took 15 days [r1.delivery_days].", late) == []
    assert kinds("Order 4243 took 15 days [r1.delivery_days].", late) == ["invented_number"]
