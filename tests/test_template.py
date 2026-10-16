import pytest

from result_explainer.explainers.template import TemplateExplainer, humanize
from result_explainer.facts import build_facts
from result_explainer.questions import QueryResult, load_questions, run_question
from result_explainer.validator import validate

QUESTIONS = load_questions()
TEMPLATE = TemplateExplainer()


@pytest.mark.parametrize("question", QUESTIONS.values(), ids=list(QUESTIONS))
def test_template_output_passes_the_validator_for_every_question(question, db_path):
    facts = build_facts(question, run_question(question, db_path))
    text = TEMPLATE.explain(facts)
    assert validate(text, facts).ok, validate(text, facts).messages()


def test_template_names_the_highest_and_lowest_rows():
    q03 = QUESTIONS["q03"]
    rows = [("North", 1008, 327496.25, 324.9), ("Central", 349, 100843.14, 288.95)]
    text = TEMPLATE.explain(build_facts(q03, QueryResult(list(q03.columns), rows)))
    assert "peaked at $327,496.25 for North [r1.net_revenue]" in text
    assert "lowest net revenue was $100,843.14 for Central [r2.net_revenue]" in text


def test_template_skips_null_values():
    q05 = QUESTIONS["q05"]
    rows = [("2025-01", 100.0, None, None), ("2025-02", 110.0, 100.0, 10.0)]
    text = TEMPLATE.explain(build_facts(q05, QueryResult(list(q05.columns), rows)))
    assert "[r1.growth_pct]" not in text
    assert "growth peaked at 10.0% for 2025-02 [r2.growth_pct]" in text.lower()


def test_template_reports_an_empty_result_without_numbers():
    q10 = QUESTIONS["q10"]
    text = TEMPLATE.explain(build_facts(q10, QueryResult(list(q10.columns), [])))
    assert text.startswith("The query returned 0 rows [meta.row_count]")


@pytest.mark.parametrize(
    ("column", "words"),
    [("avg_order_value", "average order value"), ("repeat_rate_pct", "repeat rate"), ("units_sold", "units sold")],
)
def test_humanize(column, words):
    assert humanize(column) == words
