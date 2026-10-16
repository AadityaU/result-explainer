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


@dataclass(frozen=True)
class Category:
    price_range: tuple[int, int]  # whole dollars, inclusive; every price ends in .99
    return_rate_pct: int          # chance that a delivered order line is returned
    products: tuple[str, ...]


CATEGORIES = {
    "Electronics": Category((29, 499), 5, (
        "Wireless Earbuds", "Bluetooth Speaker", "USB-C Hub", "Mechanical Keyboard",
        "HD Webcam", "Portable Charger", "Smart Plug", "Noise-Cancelling Headphones",
    )),
    "Home": Category((14, 199), 4, (
        "Ceramic Mug Set", "Linen Throw", "Cast Iron Skillet", "Desk Lamp",
        "Bamboo Cutting Board", "Scented Candle", "Wall Clock", "Storage Baskets",
    )),
    "Outdoor": Category((19, 299), 6, (
        "Trail Backpack", "Camping Stove", "Insulated Bottle", "Hammock",
        "Headlamp", "Trekking Poles", "Rain Shell", "Folding Chair",
    )),
    "Apparel": Category((19, 149), 14, (
        "Merino Tee", "Denim Jacket", "Running Shoes", "Wool Beanie",
        "Rain Boots", "Fleece Hoodie", "Chino Pants", "Leather Belt",
    )),
    "Books": Category((9, 49), 2, (
        "The Copper Lantern", "Northbound", "Salt and Cedar", "The Last Orchard",
        "Glass Harbor", "Field Notes", "Paper Moons", "The Long Table",
    )),
}


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    unit_price_cents: int


def generate_products(rng: random.Random) -> list[Product]:
    products = []
    for category, spec in CATEGORIES.items():
        low, high = spec.price_range
        for name in spec.products:
            price_cents = rng.randint(low, high) * 100 + 99
            products.append(Product(len(products) + 1, name, category, price_cents))
    return products
