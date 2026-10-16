"""Grounding checks: every number in an explanation must come from a cited fact."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

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
