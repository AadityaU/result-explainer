"""Command-line interface: generate-data | build-db | list | ask | check | evaluate | dashboard."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from result_explainer import __version__
from result_explainer.db import build_database
from result_explainer.evaluate import evaluate, evaluation_setups, render_report, summarize
from result_explainer.evaluate import render_table as render_eval_table
from result_explainer.explainers.base import Explainer, ExplainerError
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.llm import LLMSettings, llm_configured, routed_explainers
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.facts import build_facts
from result_explainer.generate import SEED, generate, write_csv
from result_explainer.paths import DATA_DIR, DEFAULT_DB, ROOT
from result_explainer.pipeline import explain_question, with_retry
from result_explainer.questions import QuestionError, get_question, load_questions, run_question
from result_explainer.render import render_explanation
from result_explainer.validator import validate


def cmd_generate_data(args: argparse.Namespace) -> int:
    for path in write_csv(generate(args.seed), DATA_DIR):
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


def cmd_build_db(args: argparse.Namespace) -> int:
    counts = build_database(args.db)
    for table, count in counts.items():
        print(f"{table:<12} {count:>6,} rows")
    print(f"built {args.db}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    for question in load_questions().values():
        print(f"{question.id}  {question.title}")
        print(f"     {question.question}")
    return 0


EXPLAINERS = ("auto", "template", "llm", "faulty")


def make_explainers(mode: str) -> list[Explainer]:
    """The explainer for each attempt.

    'auto' uses the language model when LLM_API_KEY (or a custom endpoint) is set, otherwise
    the template. Which model writes the draft and which handles a rejected draft is decided
    in explainers/llm.py, not by the user.
    """
    if mode == "auto":
        mode = "llm" if llm_configured() else "template"
    if mode == "template":
        return [TemplateExplainer()]
    if mode == "faulty":
        return with_retry(FaultyExplainer())
    return routed_explainers(LLMSettings.from_env())


def cmd_ask(args: argparse.Namespace) -> int:
    question = get_question(args.question_id)
    explanation = explain_question(question, make_explainers(args.explainer), args.db)
    print(render_explanation(explanation, show_sql=args.show_sql, show_facts=args.show_facts))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    questions = list(load_questions().values())
    results = {}
    for label, explainers in evaluation_setups(LLMSettings.from_env()).items():
        print(f"Evaluating {label} on {len(questions)} questions...", flush=True)
        rows = evaluate(explainers, questions, args.db)
        print(render_eval_table(rows))
        print(summarize(rows))
        print()
        results[label] = rows
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_report(results), encoding="utf-8")
        print(f"wrote {args.report}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    if importlib.util.find_spec("streamlit") is None:
        print('error: the dashboard needs Streamlit. Install it with: pip install -e ".[ui]"', file=sys.stderr)
        return 2
    script = Path(__file__).with_name("dashboard.py")
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(script)])


def cmd_check(args: argparse.Namespace) -> int:
    """Run every approved question read-only, check its columns, and check that the
    template explanation passes the grounding validator."""
    template = TemplateExplainer()
    questions = load_questions()
    failed = 0
    for question in questions.values():
        try:
            facts = build_facts(question, run_question(question, args.db))
            problems = validate(template.explain(facts), facts).messages()
            rows = f"{facts.row_count:>3} rows"
        except QuestionError as error:
            problems, rows = [str(error)], "  - rows"
        print(f"{question.id}  {'ok' if not problems else 'FAIL':<4}  {rows}  {question.title}")
        for problem in problems:
            print(f"      {problem}")
        failed += bool(problems)
    if failed:
        print(f"{failed} of {len(questions)} approved questions failed.")
        return 1
    print(f"All {len(questions)} approved questions run, return their declared columns "
          "and produce grounded explanations.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="result-explainer",
        description="Explain approved SQL query results without inventing numbers.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    generate_cmd = commands.add_parser(
        "generate-data", help="regenerate data/*.csv from the seeded generator"
    )
    generate_cmd.add_argument("--seed", type=int, default=SEED, help=f"random seed (default {SEED})")
    generate_cmd.set_defaults(handler=cmd_generate_data)

    build_cmd = commands.add_parser("build-db", help="build the SQLite database from data/*.csv")
    add_db_option(build_cmd)
    build_cmd.set_defaults(handler=cmd_build_db)

    list_cmd = commands.add_parser("list", help="show the approved questions")
    list_cmd.set_defaults(handler=cmd_list)

    ask_cmd = commands.add_parser("ask", help="run an approved question and explain the result")
    ask_cmd.add_argument("question_id", help="question id, e.g. q03 (see `list`)")
    ask_cmd.add_argument(
        "--explainer", choices=EXPLAINERS, default="auto",
        help="auto (default): the language model when LLM_API_KEY is set, else the template; "
             "faulty: deliberately invents numbers to show the grounding guard",
    )
    ask_cmd.add_argument("--show-sql", action="store_true", help="print the approved SQL")
    ask_cmd.add_argument("--show-facts", action="store_true", help="print every fact and its reference id")
    add_db_option(ask_cmd)
    ask_cmd.set_defaults(handler=cmd_ask)

    check_cmd = commands.add_parser(
        "check", help="validate every approved question (columns + grounded template output)"
    )
    add_db_option(check_cmd)
    check_cmd.set_defaults(handler=cmd_check)

    evaluate_cmd = commands.add_parser(
        "evaluate",
        help="run every question through each model alone and through the routed pair, "
             "and report how often each stays grounded",
    )
    evaluate_cmd.add_argument("--report", type=Path, help="also write a markdown report to this path")
    add_db_option(evaluate_cmd)
    evaluate_cmd.set_defaults(handler=cmd_evaluate)

    dashboard_cmd = commands.add_parser("dashboard", help="open the Streamlit dashboard (needs the ui extra)")
    dashboard_cmd.set_defaults(handler=cmd_dashboard)
    return parser


def add_db_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="database path (default: build/store.db)")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")  # real environment variables take precedence
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # model text on a non-UTF-8 Windows console
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError, ExplainerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
