"""Streamlit dashboard: pick an approved question, see its result and a grounded explanation.

Run with ``python -m result_explainer dashboard`` (needs ``pip install -e ".[ui]"``).
It uses the same pipeline as the CLI; nothing here computes or validates on its own.
"""

from __future__ import annotations

import html
import re
import time

import streamlit as st
from dotenv import load_dotenv

from result_explainer.db import build_database
from result_explainer.explainers.base import Explainer
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.llm import LLMSettings, llm_configured, routed_explainers
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import FactTable, build_facts
from result_explainer.paths import DEFAULT_DB, ROOT
from result_explainer.pipeline import Explanation, explain_facts, with_retry
from result_explainer.questions import QuestionError, load_questions, run_question
from result_explainer.validator import CITATION, validate

MODES = {
    "Auto": "The language model when an API key is set, otherwise the template.",
    "Template": "Deterministic summary. No model is called.",
    "Faulty (failure demo)": "A deliberately broken explainer that invents numbers, to show the guard.",
}
STATUS = {
    "grounded": ("#1a7f37", "Grounded", "Every number was matched to a cited fact from the result."),
    "fallback": ("#b35900", "Fallback", "The model's answers were rejected, so the template summary is shown."),
    "template": ("#0b5cad", "Template", "Deterministic summary. No model was used."),
    "empty": ("#57606a", "Empty result", "The query returned no rows, so no model was called."),
}
CSS = """
<style>
.badge {display: inline-block; padding: 2px 12px; border-radius: 999px; color: #fff;
        font-weight: 600; font-size: 0.85rem; margin-right: 8px;}
.explanation {font-size: 1.05rem; line-height: 1.8;}
.cite {font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.75rem;
       padding: 1px 6px; border-radius: 6px; background: rgba(11, 92, 173, 0.14);
       white-space: nowrap; cursor: help;}
</style>
"""


def safe(text: str) -> str:
    """Escape model text for HTML. '$' becomes an entity so it is never read as LaTeX."""
    return html.escape(text).replace("$", "&#36;")


@st.cache_data(show_spinner=False)
def load_facts(question_id: str) -> FactTable:
    question = load_questions()[question_id]
    return build_facts(question, run_question(question, DEFAULT_DB))


def explainers_for(mode: str) -> list[Explainer]:
    if mode == "Template" or (mode == "Auto" and not llm_configured()):
        return [TemplateExplainer()]
    if mode.startswith("Faulty"):
        return with_retry(FaultyExplainer())
    return routed_explainers(LLMSettings.from_env())


def explain(question_id: str, mode: str) -> tuple[Explanation, float]:
    """Cached for the session, so changing a display option doesn't call the model again."""
    cache = st.session_state.setdefault("explanations", {})
    key = (question_id, mode)
    if key not in cache:
        started = time.perf_counter()
        explanation = explain_facts(load_facts(question_id), explainers_for(mode))
        cache[key] = (explanation, time.perf_counter() - started)
    return cache[key]


def with_citation_chips(explanation: Explanation) -> str:
    """The explanation as HTML, each citation a chip whose tooltip shows the cited value."""
    facts = explanation.facts

    def chip(ref: str) -> str:
        fact = facts.facts.get(ref)
        where = (facts.row_label(fact.row) if fact.row else "rows returned") if fact else ""
        tip = f"{fact.display} ({where})" if fact else "unknown reference"
        return f'<span class="cite" title="{safe(tip)}">{safe(ref)}</span>'

    return CITATION.sub(
        lambda match: " ".join(chip(ref.strip()) for ref in re.split(r"[,;]", match.group(1))),
        safe(explanation.text),
    )


def result_rows(facts: FactTable) -> list[dict[str, str]]:
    return [
        {fact.column: fact.display for fact in facts.row(number)}
        for number in range(1, facts.row_count + 1)
    ]


def show_explanation(question_id: str, mode: str) -> None:
    with st.spinner("Explaining..."):
        explanation, seconds = explain(question_id, mode)
    colour, label, meaning = STATUS[explanation.status]
    st.markdown(
        f'<span class="badge" style="background:{colour}">{label}</span>{meaning}',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="explanation">{with_citation_chips(explanation)}</div>', unsafe_allow_html=True)
    attempts = len(explanation.attempts)
    st.caption(
        f"Written by {explanation.explainer} · {attempts} model attempt(s) · {seconds:.1f}s. "
        "Hover a citation to see the value it points to."
    )

    cited = explanation.cited_refs()
    if cited:
        facts = explanation.facts
        st.markdown("**Cited facts**")
        st.dataframe(
            [
                {
                    "reference": ref,
                    "value": facts.facts[ref].display,
                    "row": facts.row_label(facts.facts[ref].row) if facts.facts[ref].row else "rows returned",
                }
                for ref in cited
                if ref in facts.facts
            ],
            hide_index=True,
            use_container_width=True,
        )

    rejected = [attempt for attempt in explanation.attempts if attempt.issues]
    if rejected:
        with st.expander(f"Rejected attempts ({len(rejected)})", expanded=explanation.status == "fallback"):
            for number, attempt in enumerate(rejected, start=1):
                st.markdown(f"**Attempt {number}** from `{attempt.explainer}`")
                st.markdown(
                    f"<blockquote>{safe(attempt.text or '(no answer)')}</blockquote>",
                    unsafe_allow_html=True,
                )
                issues = "".join(f"<li><code>{issue.kind}</code>: {safe(issue.detail)}</li>" for issue in attempt.issues)
                st.markdown(f"<ul>{issues}</ul>", unsafe_allow_html=True)

    if mode != "Template" and st.button("Ask again", help="Discard the cached answer and explain again"):
        st.session_state["explanations"].pop((question_id, mode), None)
        st.rerun()


def show_question_page(questions: dict, question_id: str, mode: str, show_sql: bool, show_facts: bool) -> None:
    question = questions[question_id]
    st.subheader(f"{question.id} · {question.title}")
    st.write(question.question)
    if show_sql:
        st.code(question.sql.strip(), language="sql")

    facts = load_facts(question_id)
    st.markdown(f"**Result** · {facts.row_count} row(s)")
    if facts.is_empty:
        st.info("The query returned no rows.")
    else:
        st.dataframe(result_rows(facts), hide_index=True, use_container_width=True)
    if show_facts:
        with st.expander(f"All {len(facts.facts)} citable facts"):
            st.dataframe(
                [{"reference": f.ref, "value": f.display} for f in facts.facts.values()],
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("**Explanation**")
    show_explanation(question_id, mode)


def show_checks_page(questions: dict) -> None:
    st.subheader("Validation check")
    st.write(
        "Every approved question runs on a read-only connection, must return the columns its "
        "header declares, and its template explanation must pass the grounding validator."
    )
    rows = []
    for question in questions.values():
        try:
            facts = load_facts(question.id)
            issues = validate(TemplateExplainer().explain(facts), facts).messages()
            rows.append({"id": question.id, "question": question.title, "rows": facts.row_count,
                         "check": "ok" if not issues else "; ".join(issues)})
        except QuestionError as error:
            rows.append({"id": question.id, "question": question.title, "rows": None, "check": str(error)})
    st.dataframe(rows, hide_index=True, use_container_width=True)
    passed = sum(row["check"] == "ok" for row in rows)
    st.caption(f"{passed} of {len(rows)} questions pass.")


def main() -> None:
    st.set_page_config(page_title="SQL Result Explainer", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    load_dotenv(ROOT / ".env")
    if not DEFAULT_DB.exists():
        build_database(DEFAULT_DB)
    questions = load_questions()

    with st.sidebar:
        st.title("SQL Result Explainer")
        st.caption("Plain-language explanations of approved SQL results, with every number checked.")
        question_id = st.selectbox(
            "Approved question", list(questions), key="question",
            format_func=lambda qid: f"{qid} · {questions[qid].title}",
        )
        mode = st.radio("Explainer", list(MODES), key="mode", captions=list(MODES.values()))
        show_sql = st.toggle("Show SQL", value=False)
        show_facts = st.toggle("Show all facts", value=False)
        st.divider()
        if llm_configured():
            settings = LLMSettings.from_env()
            st.caption(f"Draft model: `{settings.draft_model}`")
            st.caption(f"Retry model (only if a draft is rejected): `{settings.retry_model}`")
        else:
            st.info("No LLM_API_KEY found, so Auto uses the template. Add your key to .env to use the model.")

    explain_tab, checks_tab = st.tabs(["Explain a question", "Validation check"])
    with explain_tab:
        show_question_page(questions, question_id, mode, show_sql, show_facts)
    with checks_tab:
        show_checks_page(questions)


main()
