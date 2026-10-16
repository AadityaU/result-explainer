"""Approved questions: one SQL file each in sql/questions/, described by header comments.

    -- id: q01
    -- title: Monthly revenue and order count
    -- question: How did net revenue ... change month by month?
    -- columns: month=label, delivered_orders=count, net_revenue=currency
    -- focus: net_revenue

These files are the only SQL the application ever runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from result_explainer.db import connect_read_only
from result_explainer.paths import DEFAULT_DB, QUESTIONS_DIR

COLUMN_TYPES = ("label", "count", "currency", "percent", "number")
HEADER_KEYS = ("id", "title", "question", "columns", "focus")
HEADER_LINE = re.compile(r"^--\s*([a-z]+):\s*(.+?)\s*$")


class QuestionError(ValueError):
    """An approved question file is malformed, or a question id is unknown."""


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    question: str
    columns: dict[str, str]  # column name -> type, in result order
    focus: str               # the main metric column
    sql: str
    path: Path


def parse_question(path: Path) -> Question:
    sql = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    for line in sql.splitlines():
        if not line.startswith("--"):
            break
        match = HEADER_LINE.match(line)
        if match and match.group(1) in HEADER_KEYS:
            meta[match.group(1)] = match.group(2)

    missing = [key for key in HEADER_KEYS if key not in meta]
    if missing:
        raise QuestionError(f"{path.name}: missing header field(s): {', '.join(missing)}")
    if not path.stem.startswith(f"{meta['id']}_"):
        raise QuestionError(f"{path.name}: file name must start with its id {meta['id']!r}")

    columns: dict[str, str] = {}
    for spec in meta["columns"].split(","):
        name, _, kind = spec.strip().partition("=")
        if kind not in COLUMN_TYPES:
            raise QuestionError(f"{path.name}: column {name!r} has unknown type {kind!r}")
        columns[name] = kind
    if meta["focus"] not in columns:
        raise QuestionError(f"{path.name}: focus {meta['focus']!r} is not a declared column")

    return Question(
        id=meta["id"],
        title=meta["title"],
        question=meta["question"],
        columns=columns,
        focus=meta["focus"],
        sql=sql,
        path=path,
    )


def load_questions(directory: Path = QUESTIONS_DIR) -> dict[str, Question]:
    questions: dict[str, Question] = {}
    for path in sorted(directory.glob("q*.sql")):
        question = parse_question(path)
        if question.id in questions:
            raise QuestionError(f"duplicate question id {question.id!r}")
        questions[question.id] = question
    return questions


def get_question(question_id: str, directory: Path = QUESTIONS_DIR) -> Question:
    questions = load_questions(directory)
    try:
        return questions[question_id.lower()]
    except KeyError:
        approved = ", ".join(questions) or "none"
        raise QuestionError(
            f"Unknown question {question_id!r}. Approved questions: {approved}"
        ) from None


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]


def run_question(question: Question, db_path: Path = DEFAULT_DB) -> QueryResult:
    """Run an approved question on a read-only connection and check its columns."""
    conn = connect_read_only(db_path)
    try:
        cursor = conn.execute(question.sql)  # sqlite3 refuses more than one statement
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
    finally:
        conn.close()
    if columns != list(question.columns):
        raise QuestionError(
            f"{question.id}: query returned columns {columns}, header declares {list(question.columns)}"
        )
    return QueryResult(columns, rows)
