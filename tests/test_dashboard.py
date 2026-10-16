import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from result_explainer.paths import ROOT  # noqa: E402

DASHBOARD = ROOT / "src" / "result_explainer" / "dashboard.py"


@pytest.fixture
def app(monkeypatch):
    # Empty values stop a local .env from switching the dashboard to the real model.
    for name in ("LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.setenv(name, "")
    return AppTest.from_file(str(DASHBOARD), default_timeout=60).run()


def page_html(app):
    return "\n".join(block.value for block in app.markdown)


def test_dashboard_explains_the_first_question_with_the_template(app):
    assert not app.exception
    assert app.selectbox(key="question").value == "q01"
    assert "Template" in page_html(app)
    assert 'class="cite"' in page_html(app)


def test_dashboard_shows_rejected_attempts_for_the_faulty_explainer(app):
    app.radio(key="mode").set_value("Faulty (failure demo)").run()
    assert not app.exception
    assert "Fallback" in page_html(app)
    assert any(expander.label.startswith("Rejected attempts") for expander in app.expander)


def test_dashboard_handles_the_empty_result(app):
    app.selectbox(key="question").set_value("q10").run()
    assert not app.exception
    assert "Empty result" in page_html(app)
