from result_explainer.evaluate import evaluate, render_report, render_table, summarize
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.questions import load_questions

QUESTIONS = load_questions()


class CopyingExplainer:
    """Behaves like a model that always writes a grounded answer."""

    name = "copying"

    def explain(self, facts, feedback=None):
        return TemplateExplainer().explain(facts)


def test_evaluate_keeps_question_order_and_skips_empty_results(db_path):
    rows = evaluate(CopyingExplainer(), list(QUESTIONS.values()), db_path)
    assert [row.explanation.question.id for row in rows] == list(QUESTIONS)
    assert summarize(rows) == "9/9 grounded (9 on the first attempt), 0 fallback, 1 empty result(s) skipped"


def test_evaluate_counts_fallbacks_and_reports_rejected_attempts(db_path):
    rows = evaluate(FaultyExplainer(), [QUESTIONS["q03"], QUESTIONS["q10"]], db_path)
    assert summarize(rows) == "0/1 grounded (0 on the first attempt), 1 fallback, 1 empty result(s) skipped"
    assert "invented_number" in render_table(rows)
    report = render_report({"faulty": rows})
    assert "### q03: Revenue and average order value by region" in report
    assert "Rejected attempt 1" in report
