"""Command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from result_explainer import __version__
from result_explainer.db import build_database
from result_explainer.explainers.base import Explainer, ExplainerError
from result_explainer.explainers.faulty import FaultyExplainer
from result_explainer.explainers.llm import LLMExplainer, LLMSettings
from result_explainer.explainers.template import TemplateExplainer
from result_explainer.generate import SEED, generate, write_csv
from result_explainer.paths import DATA_DIR, DEFAULT_DB, ROOT
from result_explainer.pipeline import explain_question
from result_explainer.questions import get_question, load_questions
from result_explainer.render import render_explanation


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


def make_explainer(name: str) -> Explainer:
    """'auto' uses the LLM when LLM_BASE_URL is configured, otherwise the template."""
    if name == "auto":
        name = "llm" if os.environ.get("LLM_BASE_URL", "").strip() else "template"
    if name == "template":
        return TemplateExplainer()
    if name == "faulty":
        return FaultyExplainer()
    return LLMExplainer(LLMSettings.from_env())


def cmd_ask(args: argparse.Namespace) -> int:
    question = get_question(args.question_id)
    explanation = explain_question(question, make_explainer(args.explainer), args.db)
    print(render_explanation(explanation, show_sql=args.show_sql, show_facts=args.show_facts))
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
        help="auto (default): llm if LLM_BASE_URL is set, else template; "
             "faulty: deliberately invents numbers to show the grounding guard",
    )
    ask_cmd.add_argument("--show-sql", action="store_true", help="print the approved SQL")
    ask_cmd.add_argument("--show-facts", action="store_true", help="print every fact and its reference id")
    add_db_option(ask_cmd)
    ask_cmd.set_defaults(handler=cmd_ask)
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
