"""Run every approved question through an explainer and report how often it stays grounded."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from result_explainer.explainers.base import Explainer
from result_explainer.paths import DEFAULT_DB
from result_explainer.pipeline import Explanation, explain_question
from result_explainer.questions import Question


@dataclass(frozen=True)
class EvalRow:
    explanation: Explanation
    seconds: float

    @property
    def attempts(self) -> int:
        return len(self.explanation.attempts)

    @property
    def issue_kinds(self) -> list[str]:
        return [issue.kind for attempt in self.explanation.attempts for issue in attempt.issues]


def evaluate(
    explainer: Explainer, questions: list[Question], db_path: Path = DEFAULT_DB, workers: int = 5
) -> list[EvalRow]:
    """Explain each question (in parallel; results keep the question order)."""
    def run(question: Question) -> EvalRow:
        started = time.perf_counter()
        explanation = explain_question(question, explainer, db_path)
        return EvalRow(explanation, time.perf_counter() - started)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, questions))


def summarize(rows: list[EvalRow]) -> str:
    asked = [row for row in rows if row.explanation.status != "empty"]
    grounded = [row for row in asked if row.explanation.status == "grounded"]
    first_try = [row for row in grounded if row.attempts == 1]
    empty = len(rows) - len(asked)
    return (
        f"{len(grounded)}/{len(asked)} grounded ({len(first_try)} on the first attempt), "
        f"{len(asked) - len(grounded)} fallback, {empty} empty result(s) skipped"
    )


def render_table(rows: list[EvalRow]) -> str:
    lines = [f"{'id':<4}  {'status':<9}  {'attempts':>8}  {'seconds':>7}  issues"]
    for row in rows:
        issues = ", ".join(sorted(set(row.issue_kinds))) or "-"
        lines.append(
            f"{row.explanation.question.id:<4}  {row.explanation.status:<9}  "
            f"{row.attempts:>8}  {row.seconds:>7.1f}  {issues}"
        )
    return "\n".join(lines)


def render_report(results: dict[str, list[EvalRow]]) -> str:
    """A markdown report with every final explanation and every rejected attempt."""
    lines = ["# Model evaluation", ""]
    lines += ["| Model | Result |", "|-------|--------|"]
    lines += [f"| `{model}` | {summarize(rows)} |" for model, rows in results.items()]
    for model, rows in results.items():
        lines += ["", f"## `{model}`", "", "```text", render_table(rows), "```"]
        for row in rows:
            explanation = row.explanation
            question = explanation.question
            lines += ["", f"### {question.id}: {question.title}", ""]
            lines += [f"**{explanation.status}** after {row.attempts} attempt(s), {row.seconds:.1f}s", ""]
            lines += [f"> {explanation.text}"]
            for number, attempt in enumerate(explanation.attempts, start=1):
                if attempt.issues:
                    lines += ["", f"Rejected attempt {number}: {attempt.text or '(no answer)'}", ""]
                    lines += [f"- `{issue.kind}`: {issue.detail}" for issue in attempt.issues]
    return "\n".join(lines) + "\n"
