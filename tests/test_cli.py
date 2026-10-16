import pytest

from result_explainer import cli


@pytest.fixture(autouse=True)
def no_llm_config(monkeypatch):
    """Ignore any local .env so tests behave the same on every machine."""
    monkeypatch.setattr(cli, "load_dotenv", lambda *args, **kwargs: None)
    for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)


def run(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_no_command_prints_help(capsys):
    code, out, _ = run(capsys)
    assert code == 1
    assert "ask" in out


def test_build_db_creates_the_database(capsys, tmp_path):
    db = tmp_path / "store.db"
    code, out, _ = run(capsys, "build-db", "--db", str(db))
    assert code == 0
    assert db.exists()
    assert "orders" in out


def test_list_shows_every_approved_question(capsys):
    code, out, _ = run(capsys, "list")
    assert code == 0
    assert all(f"q{n:02d}" in out for n in range(1, 11))


def test_ask_without_llm_config_uses_the_template(capsys, db_path):
    code, out, _ = run(capsys, "ask", "q03", "--db", str(db_path))
    assert code == 0
    assert "Explanation (template" in out
    assert "Cited facts" in out
    assert "[r1.net_revenue]" in out


def test_ask_shows_sql_and_facts_on_request(capsys, db_path):
    code, out, _ = run(capsys, "ask", "q01", "--show-sql", "--show-facts", "--db", str(db_path))
    assert code == 0
    assert "SELECT" in out
    assert "[meta.row_count] = 12" in out


def test_faulty_explainer_is_rejected_and_shown(capsys, db_path):
    code, out, _ = run(capsys, "ask", "q03", "--explainer", "faulty", "--db", str(db_path))
    assert code == 0
    assert "Explanation (fallback" in out
    assert "Rejected attempts" in out
    assert "invented_number" in out


def test_empty_result_is_explained_without_a_model(capsys, db_path):
    code, out, _ = run(capsys, "ask", "q10", "--explainer", "faulty", "--db", str(db_path))
    assert code == 0
    assert "(no rows)" in out
    assert "the model was not called" in out


def test_llm_without_config_is_a_clear_error(capsys, db_path):
    code, _, err = run(capsys, "ask", "q01", "--explainer", "llm", "--db", str(db_path))
    assert code == 2
    assert "LLM_BASE_URL" in err


def test_unknown_question_is_a_clear_error(capsys, db_path):
    code, _, err = run(capsys, "ask", "q42", "--db", str(db_path))
    assert code == 2
    assert "Approved questions" in err


def test_missing_database_says_how_to_build_it(capsys, tmp_path):
    code, _, err = run(capsys, "ask", "q01", "--db", str(tmp_path / "missing.db"))
    assert code == 2
    assert "build-db" in err


def test_check_passes_on_the_sample_data(capsys, db_path):
    code, out, _ = run(capsys, "check", "--db", str(db_path))
    assert code == 0
    assert out.count(" ok ") == 10
