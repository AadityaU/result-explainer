from result_explainer.explainers.base import ExplainerError
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import build_facts
from result_explainer.pipeline import explain_facts, explain_question
from result_explainer.questions import QueryResult, load_questions

QUESTIONS = load_questions()
Q06 = QUESTIONS["q06"]
FACTS = build_facts(Q06, QueryResult(list(Q06.columns), [(1722, 956, 55.5)]))
GOOD = "55.5% of customers came back [r1.repeat_rate_pct]."
BAD = "70.0% of customers came back [r1.repeat_rate_pct]."


class ScriptedExplainer:
    """Returns prepared answers in order and records the feedback it was given."""

    name = "scripted"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.feedback = []

    def explain(self, facts, feedback=None):
        self.feedback.append(feedback)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_grounded_answer_is_accepted_on_the_first_attempt():
    explanation = explain_facts(FACTS, ScriptedExplainer(GOOD))
    assert (explanation.status, explanation.explainer, explanation.text) == ("grounded", "scripted", GOOD)
    assert len(explanation.attempts) == 1


def test_rejected_answer_is_retried_with_the_validator_feedback():
    explainer = ScriptedExplainer(BAD, GOOD)
    explanation = explain_facts(FACTS, explainer)
    assert explanation.status == "grounded"
    assert explainer.feedback[0] is None
    assert any("70.0%" in message for message in explainer.feedback[1])


def test_two_rejections_fall_back_to_the_template():
    explanation = explain_facts(FACTS, ScriptedExplainer(BAD, BAD))
    assert (explanation.status, explanation.explainer) == ("fallback", "template")
    assert explanation.text == TemplateExplainer().explain(FACTS)
    assert [attempt.text for attempt in explanation.attempts] == [BAD, BAD]


def test_explainer_errors_fall_back_without_retrying():
    explainer = ScriptedExplainer(ExplainerError("endpoint down"), GOOD)
    explanation = explain_facts(FACTS, explainer)
    assert explanation.status == "fallback"
    assert explanation.attempts[0].issues == ["explainer_error: endpoint down"]
    assert len(explainer.feedback) == 1


def test_empty_result_never_reaches_the_explainer(db_path):
    explainer = ScriptedExplainer()  # would fail if it were called
    explanation = explain_question(QUESTIONS["q10"], explainer, db_path)
    assert explanation.status == "empty"
    assert explainer.feedback == []
    assert explanation.cited_refs() == ["meta.row_count"]


def test_faulty_explainer_is_always_caught(db_path):
    explanation = explain_question(QUESTIONS["q03"], FaultyExplainer(), db_path)
    assert explanation.status == "fallback"
    issues = [issue for attempt in explanation.attempts for issue in attempt.issues]
    assert any(issue.startswith("invented_number") for issue in issues)
    assert any(issue.startswith("unsupported_calculation") for issue in issues)


def test_template_can_be_chosen_directly(db_path):
    explanation = explain_question(QUESTIONS["q01"], TemplateExplainer(), db_path)
    assert (explanation.status, explanation.attempts) == ("template", [])
