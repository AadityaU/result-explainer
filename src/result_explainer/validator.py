"""Grounding checks: every number in an explanation must come from a cited fact."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from result_explainer.facts import FactTable
from result_explainer.formatting import round_half_up

# A number as people write it: optional $, digits with optional thousands separators
# and decimals, then an optional %, k or M. A letter, digit or dot right before it
# (Q4, r3, v1.2) means it belongs to a word, not a standalone number.
NUMBER = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:\s?(%)|([kKmM])\b)?")
SCALE = {"k": Decimal(1_000), "m": Decimal(1_000_000)}
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class NumberMention:
    text: str
    written: Decimal  # absolute value as written, before any k/M scale
    decimals: int     # decimal places as written
    scale: Decimal

    def matches(self, value: Decimal) -> bool:
        """True if this is `value`, possibly rounded or abbreviated (85,657.45 -> 85.7k)."""
        return round_half_up(abs(value) / self.scale, self.decimals) == self.written


def extract_numbers(text: str) -> list[NumberMention]:
    mentions = []
    for match in NUMBER.finditer(text):
        whole, fraction, _percent, suffix = match.groups()
        written = Decimal(whole.replace(",", "") + (fraction or ""))
        decimals = len(fraction) - 1 if fraction else 0
        scale = SCALE[suffix.lower()] if suffix else Decimal(1)
        mentions.append(NumberMention(match.group(0).strip(), written, decimals, scale))
    return mentions


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_BREAK.split(text) if part.strip()]


CITATION = re.compile(r"\[(r\d+\.[a-z_]+|meta\.[a-z_]+)\]")


@dataclass(frozen=True)
class Issue:
    kind: str
    detail: str
    sentence: str = ""

    def __str__(self) -> str:
        where = f' in "{self.sentence}"' if self.sentence else ""
        return f"{self.kind}: {self.detail}{where}"


@dataclass(frozen=True)
class ValidationResult:
    issues: list[Issue]

    @property
    def ok(self) -> bool:
        return not self.issues

    def messages(self) -> list[str]:
        return [str(issue) for issue in self.issues]


def validate(text: str, facts: FactTable) -> ValidationResult:
    if not text.strip():
        return ValidationResult([Issue("empty", "the explanation is empty")])

    issues: list[Issue] = []
    cited_any = False
    for sentence in split_sentences(text):
        for ref in CITATION.findall(sentence):
            if ref in facts.facts:
                cited_any = True
            else:
                issues.append(Issue("unknown_reference", f"[{ref}] is not in the result", sentence))

    if not facts.is_empty and not cited_any:
        issues.append(Issue("no_citations", "the explanation does not cite any returned metric"))
    return ValidationResult(issues)
