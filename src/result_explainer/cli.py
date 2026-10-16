"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from result_explainer import __version__
from result_explainer.db import build_database
from result_explainer.generate import SEED, generate, write_csv
from result_explainer.paths import DATA_DIR, DEFAULT_DB, ROOT
from result_explainer.questions import load_questions


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
    return parser


def add_db_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="database path (default: build/store.db)")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
