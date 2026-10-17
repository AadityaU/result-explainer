import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from result_explainer.paths import ROOT  # noqa: E402

DASHBOARD = ROOT / "src" / "result_explainer" / "dashboard.py"


def start(monkeypatch, api_key=""):
    # An explicit value stops a local .env from deciding whether the model is configured.
    monkeypatch.setenv("LLM_API_KEY", api_key)
    monkeypatch.setenv("LLM_BASE_URL", "")
    return AppTest.from_file(str(DASHBOARD), default_timeout=60)


@pytest.fixture
def app(monkeypatch):
    return start(monkeypatch).run()


def page_html(app):
    return "\n".join(block.value for block in app.markdown)


def test_without_a_key_the_template_explains_the_first_question(app):
    assert not app.exception
    assert app.selectbox(key="question").value == "q01"
    assert "Template" in page_html(app)
    assert 'class="cite"' in page_html(app)


def test_with_a_key_the_model_waits_for_a_click(monkeypatch):
    app = start(monkeypatch, api_key="sk-test").run()
    assert not app.exception
    assert [button.label for button in app.button] == ["Explain with the language model"]
    assert 'class="badge"' not in page_html(app)  # nothing explained, no model called


def test_model_calls_stop_at_the_session_cap(monkeypatch):
    app = start(monkeypatch, api_key="sk-test")
    app.session_state["model_calls"] = 20
    app.run()
    assert not app.exception
    assert "model explanations" in app.warning[0].value
    assert not app.button


def test_intro_and_how_it_works_describe_the_project(app):
    labels = [metric.label for metric in app.metric]
    assert labels == ["Approved questions", "Rows of synthetic data", "Rules checked per answer", "Grounded in evaluation"]
    assert app.metric[0].value == "10"
    text = page_html(app)
    assert "What the validator rejects" in text
    assert "Which model does what" in text


def test_dataset_tab_lists_tables_and_previews_rows(app):
    text = page_html(app)
    assert "Metric definitions" in text
    assert "| `orders` | 4,310 |" in text
    app.selectbox(key="preview_table").set_value("orders").run()
    assert not app.exception
    preview = app.dataframe[-2].value  # the table preview, before the validation-check table
    assert list(preview.columns)[:3] == ["order_id", "customer_id", "order_date"]
    assert len(preview) == 20


def test_faulty_explainer_shows_rejected_attempts(app):
    app.radio(key="mode").set_value("Faulty (failure demo)").run()
    assert not app.exception
    assert "Fallback" in page_html(app)
    assert any(expander.label.startswith("Rejected attempts") for expander in app.expander)


def test_empty_result_is_explained_without_a_model(app):
    app.selectbox(key="question").set_value("q10").run()
    assert not app.exception
    assert "Empty result" in page_html(app)
