import pytest

from result_explainer.questions import (
    QuestionError,
    get_question,
    load_questions,
    parse_question,
    run_question,
)

QUESTIONS = load_questions()


def test_ten_approved_questions_are_loaded():
    assert list(QUESTIONS) == [f"q{n:02d}" for n in range(1, 11)]


@pytest.mark.parametrize("question", QUESTIONS.values(), ids=list(QUESTIONS))
def test_question_runs_and_returns_declared_columns(question, db_path):
    result = run_question(question, db_path)
    assert result.columns == list(question.columns)


@pytest.mark.parametrize("question_id", [q for q in QUESTIONS if q != "q10"])
def test_questions_return_rows(question_id, db_path):
    assert run_question(QUESTIONS[question_id], db_path).rows


def test_q10_is_empty_because_every_delivery_met_the_promise(db_path):
    assert run_question(QUESTIONS["q10"], db_path).rows == []


def test_q05_first_month_has_no_growth(db_path):
    first = run_question(QUESTIONS["q05"], db_path).rows[0]
    assert first[0] == "2025-01"
    assert first[2] is None and first[3] is None


def test_q04_shares_cover_all_revenue(db_path):
    shares = [row[3] for row in run_question(QUESTIONS["q04"], db_path).rows]
    assert sum(shares) == pytest.approx(100, abs=0.2)


def test_unknown_question_lists_the_approved_ones():
    with pytest.raises(QuestionError, match="q01"):
        get_question("q99")


def test_header_must_declare_every_field(tmp_path):
    path = tmp_path / "q11_broken.sql"
    path.write_text("-- id: q11\n-- title: Broken\nSELECT 1;\n", encoding="utf-8")
    with pytest.raises(QuestionError, match="missing header"):
        parse_question(path)


def test_column_types_are_checked(tmp_path):
    path = tmp_path / "q11_bad_type.sql"
    path.write_text(
        "-- id: q11\n-- title: T\n-- question: Q?\n-- columns: x=money\n-- focus: x\nSELECT 1 AS x;\n",
        encoding="utf-8",
    )
    with pytest.raises(QuestionError, match="unknown type"):
        parse_question(path)


def test_column_mismatch_is_reported(tmp_path, db_path):
    path = tmp_path / "q11_mismatch.sql"
    path.write_text(
        "-- id: q11\n-- title: T\n-- question: Q?\n-- columns: x=count\n-- focus: x\nSELECT 1 AS y;\n",
        encoding="utf-8",
    )
    with pytest.raises(QuestionError, match="header declares"):
        run_question(parse_question(path), db_path)
