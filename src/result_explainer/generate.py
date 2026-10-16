"""Seeded generator for the synthetic online-store dataset.

Every value comes from a single ``random.Random(seed)`` and integer weights, so the
same seed always produces byte-identical CSV files. Money is integer cents and dates
are ISO-8601 text.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypeVar

T = TypeVar("T")

SEED = 42
YEAR = 2025

CUSTOMER_COUNT = 600
SIGNUP_START = date(2023, 1, 1)
SIGNUP_END = date(2025, 11, 30)

REGIONS = {"North": 24, "South": 22, "East": 26, "West": 20, "Central": 8}
SEGMENTS = {"consumer": 80, "business": 20}
# How often a customer buys relative to others: most buy rarely, a few buy a lot.
ACTIVITY = {1: 50, 2: 30, 4: 15, 8: 5}


@dataclass(frozen=True)
class Customer:
    customer_id: int
    region: str
    segment: str
    signup_date: str


def pick(rng: random.Random, weights: dict[T, int]) -> T:
    """Pick one key from a ``{value: weight}`` mapping."""
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def generate_customers(rng: random.Random) -> tuple[list[Customer], dict[int, int]]:
    """Return the customers and each customer's buying activity weight."""
    customers = []
    activity = {}
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        customers.append(
            Customer(
                customer_id=customer_id,
                region=pick(rng, REGIONS),
                segment=pick(rng, SEGMENTS),
                signup_date=random_date(rng, SIGNUP_START, SIGNUP_END).isoformat(),
            )
        )
        activity[customer_id] = pick(rng, ACTIVITY)
    return customers, activity
