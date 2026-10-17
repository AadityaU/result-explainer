"""Streamlit dashboard: pick an approved question, see its result and a grounded explanation.

Run with ``python -m result_explainer dashboard`` (needs ``pip install -e ".[ui]"``).
It uses the same pipeline as the CLI; nothing here computes or validates on its own.
"""

from __future__ import annotations

import html
import re
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Hosts such as Streamlit Community Cloud run this file directly without installing the
# package, so make src/ importable. With an editable install this is the same path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from result_explainer.db import build_database, connect_read_only
from result_explainer.explainers.base import Explainer
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.llm import (
    DRAFT_MODEL,
    RETRY_MODEL,
    LLMSettings,
    llm_configured,
    routed_explainers,
)
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import FactTable, build_facts
from result_explainer.generate import TABLES
from result_explainer.paths import DEFAULT_DB, ROOT
from result_explainer.pipeline import Explanation, explain_facts, with_retry
from result_explainer.questions import QuestionError, load_questions, run_question
from result_explainer.validator import CITATION, validate

MODES = {
    "Language model": "Explained by the model when an API key is set, otherwise by the template.",
    "Template": "Deterministic summary. No model is called.",
    "Faulty (failure demo)": "A deliberately broken explainer that invents numbers, to show the guard.",
}
# A public deployment spends the owner's API credit, so the model only runs on request and
# each visitor session gets a limited number of model explanations.
MODEL_CALLS_PER_SESSION = 20
REPO_URL = "https://github.com/AadityaU/result-explainer"

ISSUE_RULES = [
    ("invented_number", "A number that matches no value in the result"),
    ("uncited_number", "A real value, but not held by any fact cited in the same sentence"),
    ("mismatched_label", "The sentence names a row (a region, month, product) that none of its citations belong to"),
    ("unsupported_calculation", "Words like doubled, twice or 3x that imply math the query didn't do"),
    ("unknown_reference", "A citation id that doesn't exist"),
    ("no_citations", "A non-empty result explained without citing anything"),
]
HOW_IT_WORKS = """
1. **Approved SQL only.** Ten reviewed queries live in `sql/questions/`. The model never writes
   SQL, and the database is opened read-only.
2. **SQL does the math.** Growth, shares, averages and rates are computed in the query, so the
   model only describes values it is given.
3. **Every value gets an id.** Each cell of the result becomes a fact such as `[r3.net_revenue]`,
   and the explanation must cite these ids.
4. **Every sentence is checked.** Each number must match a fact cited in the same sentence, and
   every row the sentence names must be one it cites.
5. **Retry, then fall back.** A rejected draft goes to a second model, with the issues found. If
   that also fails, a deterministic template summary is shown, clearly labelled.
"""
DRAFT_WHY = "grounded on all 36 evaluated answers, never slower than 13.2 s"
RETRY_WHY = "just as grounded and about 4x cheaper, but sometimes slow: an independent second opinion"
TABLE_NOTES = {
    "customers": "Each customer's region and segment (consumer or business)",
    "products": "40 products in five categories, with prices",
    "orders": "Order date, sales channel and status; cancelled orders have no delivery date",
    "order_items": "Order lines: quantity, price at the time of the order and discount",
    "returns": "Units sent back from an order line, with the reason",
}
METRIC_DEFINITIONS = """
- **Net revenue**: quantity × unit price × (100 − discount %) / 100, delivered orders only, before returns.
- **Average order value**: net revenue ÷ delivered orders.
- **Return rate**: units returned ÷ units sold on delivered orders.
- **Repeat customer**: a customer with two or more delivered orders.
- **New customer in a quarter**: the customer's first delivered order falls in that quarter.
- **Delivery days**: days from the order date to the delivery date.
"""
LIMITATIONS = """
The validator checks numbers, citations and the rows a sentence names. It does not check
direction words ("rose" vs "fell"), claims that contain no number or row name, or month names
written out ("March" instead of `2025-03`). The prompt asks the model to get these right, but
nothing enforces them.
"""
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


def uses_model(mode: str) -> bool:
    return mode == "Language model" and llm_configured()


def explainers_for(mode: str) -> list[Explainer]:
    if mode == "Template" or (mode == "Language model" and not llm_configured()):
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


def model_call_allowed(question_id: str, mode: str) -> bool:
    """Free explainers run straight away; the model runs only when asked, within the cap."""
    cached = (question_id, mode) in st.session_state.get("explanations", {})
    if not uses_model(mode) or cached:
        return True
    used = st.session_state.get("model_calls", 0)
    if used >= MODEL_CALLS_PER_SESSION:
        st.warning(
            f"This session has used its {MODEL_CALLS_PER_SESSION} model explanations. "
            "The Template and Faulty explainers still work."
        )
        return False
    st.caption("The model is only called when you ask, so browsing the questions costs nothing.")
    if not st.button("Explain with the language model", type="primary", key=f"ask_{question_id}"):
        return False
    st.session_state["model_calls"] = used + 1
    return True


def show_explanation(question_id: str, mode: str) -> None:
    if not model_call_allowed(question_id, mode):
        return
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
        f"Written by {explanation.explainer} · {attempts} attempt(s) checked · {seconds:.1f}s. "
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

    if uses_model(mode) and st.button("Ask again", help="Discard this answer and ask the model again"):
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


@st.cache_data(show_spinner=False)
def table_counts() -> dict[str, int]:
    conn = connect_read_only(DEFAULT_DB)
    try:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}
    finally:
        conn.close()


def show_intro(questions: dict) -> None:
    st.markdown("## Explaining SQL results without inventing numbers")
    st.write(
        "Pick one of the approved analytics questions about a fictional online store. The query "
        "runs read-only, a language model explains the result in plain language, and every number "
        "in its answer is checked against the rows the query returned before you see it. An "
        "answer that fails the check is retried once and otherwise replaced by a deterministic "
        "summary, so what you read is always grounded in the data."
    )
    first, second, third, fourth = st.columns(4)
    first.metric("Approved questions", len(questions))
    second.metric("Rows of synthetic data", f"{sum(table_counts().values()):,}")
    third.metric("Rules checked per answer", len(ISSUE_RULES))
    fourth.metric(
        "Grounded in evaluation", "36 / 36",
        help="Answers from the draft model across every evaluation run (docs/model-evaluation.md).",
    )


def models_in_use() -> tuple[str, str]:
    if llm_configured():
        settings = LLMSettings.from_env()
        return settings.draft_model, settings.retry_model
    return DRAFT_MODEL, RETRY_MODEL


def pipeline_dot(draft: str, retry: str) -> str:
    return f"""
digraph {{
  rankdir=TB; bgcolor="transparent"; nodesep=0.6; ranksep=0.45;
  node [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#0b5cad",
        fontname="Helvetica", fontsize=13, fontcolor="#1f2328", margin="0.15,0.08"];
  edge [color="#8a94a6", fontcolor="#8a94a6", fontname="Helvetica", fontsize=11];
  {{ rank=same; question; sql; facts; }}
  {{ rank=same; draft; check1; answer; }}
  {{ rank=same; retry; check2; template; }}
  question [label="Approved question\\n(reviewed .sql file)"];
  sql [label="Run SQL\\nread-only"];
  facts [label="Fact table\\nvalue + id per cell"];
  draft [label="Draft model\\n{draft}"];
  check1 [label="Validator", shape=diamond];
  retry [label="Retry model\\n{retry}"];
  check2 [label="Validator", shape=diamond];
  template [label="Template\\nsummary"];
  answer [label="Explanation\\nwith citations", fillcolor="#e6f4ea", color="#1a7f37"];
  question -> sql -> facts -> draft -> check1;
  check1 -> answer [label="pass"];
  check1 -> retry [label="fail + issues"];
  retry -> check2;
  check2 -> answer [label="pass"];
  check2 -> template [label="fail"];
  facts -> template [label="no rows"];
  template -> answer;
}}"""


def show_how_it_works_page() -> None:
    draft, retry = models_in_use()
    st.subheader("How it works")
    st.graphviz_chart(pipeline_dot(draft, retry))
    st.markdown(HOW_IT_WORKS)

    st.markdown("#### What the validator rejects")
    st.dataframe(
        [{"issue": kind, "meaning": meaning} for kind, meaning in ISSUE_RULES],
        hide_index=True, use_container_width=True,
    )

    st.markdown("#### Which model does what")
    draft_why = DRAFT_WHY if draft == DRAFT_MODEL else "set in the environment"
    retry_why = RETRY_WHY if retry == RETRY_MODEL else "set in the environment"
    st.markdown(
        "| Role | Model | Runs | Why |\n|---|---|---|---|\n"
        f"| Draft | `{draft}` | for every first answer | {draft_why} |\n"
        f"| Retry | `{retry}` | only if the draft fails a check, errors or misses the 45 s deadline "
        f"| {retry_why} |"
    )

    st.markdown("#### Known limitations")
    st.markdown(LIMITATIONS)
    st.markdown(
        f"More detail: [code on GitHub]({REPO_URL}) · "
        f"[design note]({REPO_URL}/blob/main/docs/design-note.md) · "
        f"[model evaluation]({REPO_URL}/blob/main/docs/model-evaluation.md)"
    )


@st.cache_data(show_spinner=False)
def table_columns() -> dict[str, list[tuple[str, bool]]]:
    """(column name, is primary key) for every table, read from the database itself."""
    conn = connect_read_only(DEFAULT_DB)
    try:
        return {
            table: [(row[1], bool(row[5])) for row in conn.execute(f"PRAGMA table_info({table})")]
            for table in TABLES
        }
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def preview_rows(table: str, limit: int = 20) -> list[dict]:
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}")
    conn = connect_read_only(DEFAULT_DB)
    try:
        cursor = conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def schema_dot() -> str:
    nodes = []
    for table, columns in table_columns().items():
        lines = "".join(f"{name}{' (PK)' if is_key else ''}\\l" for name, is_key in columns)
        nodes.append(f'  {table} [label="{table}\\l\\l{lines}"];')
    return "\n".join([
        "digraph {",
        '  rankdir=LR; bgcolor="transparent"; nodesep=0.4; ranksep=0.7;',
        '  node [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#0b5cad",',
        '        fontname="Helvetica", fontsize=12, fontcolor="#1f2328", margin="0.2,0.1"];',
        '  edge [color="#8a94a6", fontcolor="#8a94a6", fontname="Helvetica", fontsize=11];',
        *nodes,
        '  customers -> orders [label="places"];',
        '  orders -> order_items [label="contains"];',
        '  products -> order_items [label="sold as"];',
        '  order_items -> returns [label="returned as"];',
        "}",
    ])


def show_dataset_page() -> None:
    st.subheader("Dataset")
    st.write(
        "A fictional online store's activity in 2025, generated from a fixed seed, so the same "
        "data is rebuilt byte for byte on every machine. Everything is synthetic: no real people, "
        "products or companies. Money is stored in integer cents."
    )
    counts = table_counts()
    st.markdown(
        "| Table | Rows | What it holds |\n|---|---:|---|\n"
        + "\n".join(f"| `{table}` | {counts[table]:,} | {TABLE_NOTES[table]} |" for table in TABLES)
    )
    st.graphviz_chart(schema_dot())
    st.markdown("#### Metric definitions")
    st.markdown(METRIC_DEFINITIONS)
    st.markdown("#### Preview a table")
    table = st.selectbox("Table", TABLES, key="preview_table", label_visibility="collapsed")
    st.dataframe(preview_rows(table), hide_index=True, use_container_width=True)
    st.caption("The first 20 rows, read through the same read-only connection the questions use.")


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
            st.info(
                "No LLM_API_KEY is set, so the template explains instead of the model. "
                "Add a key to .env (or the host's environment) to use the model."
            )
        st.link_button("View the code on GitHub", REPO_URL)

    show_intro(questions)
    explain_tab, how_tab, data_tab, checks_tab = st.tabs(
        ["Explain a question", "How it works", "Dataset", "Validation check"]
    )
    with explain_tab:
        show_question_page(questions, question_id, mode, show_sql, show_facts)
    with how_tab:
        show_how_it_works_page()
    with data_tab:
        show_dataset_page()
    with checks_tab:
        show_checks_page(questions)


main()
