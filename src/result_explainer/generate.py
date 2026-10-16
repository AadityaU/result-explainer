"""Seeded generator for the synthetic online-store dataset.

Every value comes from a single ``random.Random(seed)`` and integer weights, so the
same seed always produces byte-identical CSV files. Money is integer cents and dates
are ISO-8601 text.
"""

from __future__ import annotations

import calendar
import csv
import random
from bisect import bisect_right
from dataclasses import astuple, dataclass, fields
from datetime import date, timedelta
from itertools import accumulate
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

SEED = 42
YEAR = 2025

CUSTOMER_COUNT = 2500
SIGNUP_START = date(2023, 1, 1)
SIGNUP_END = date(2025, 11, 30)

REGIONS = {"North": 24, "South": 22, "East": 26, "West": 20, "Central": 8}
SEGMENTS = {"consumer": 80, "business": 20}
# How often a customer buys relative to others: most buy rarely, a few buy a lot.
ACTIVITY = {1: 70, 2: 18, 4: 9, 8: 3}


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


# Orders placed per month: steady through the year, peaking for the holidays.
MONTH_ORDERS = {
    1: 280, 2: 260, 3: 315, 4: 330, 5: 350, 6: 330,
    7: 315, 8: 330, 9: 350, 10: 385, 11: 505, 12: 560,
}
CHANNELS = {"web": 55, "mobile": 30, "marketplace": 15}
CANCEL_RATE_PCT = 6
SHIPPING_DAYS = (0, 2)
# Days from shipping to delivery, by region. With at most 2 days to ship, no order
# takes longer than 11 days, so the 14-day delivery promise is never missed.
DELIVERY_DAYS = {"North": (2, 5), "South": (3, 6), "East": (2, 4), "West": (3, 7), "Central": (4, 9)}


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: str
    channel: str
    status: str
    ship_date: str | None
    delivery_date: str | None


def generate_orders(
    rng: random.Random, customers: list[Customer], activity: dict[int, int]
) -> list[Order]:
    # A customer can only order after signing up: sort by signup date so the
    # eligible customers for any order date are a prefix of this list.
    by_signup = sorted(customers, key=lambda c: c.signup_date)
    signup_dates = [c.signup_date for c in by_signup]
    cum_weights = list(accumulate(activity[c.customer_id] for c in by_signup))

    placed: list[tuple[date, Customer]] = []
    for month, count in MONTH_ORDERS.items():
        last_day = calendar.monthrange(YEAR, month)[1]
        for _ in range(count):
            order_date = date(YEAR, month, rng.randint(1, last_day))
            eligible = bisect_right(signup_dates, order_date.isoformat())
            customer = rng.choices(by_signup[:eligible], cum_weights=cum_weights[:eligible])[0]
            placed.append((order_date, customer))
    placed.sort(key=lambda item: item[0])  # stable sort: same-day orders keep their order

    orders = []
    for order_id, (order_date, customer) in enumerate(placed, start=1):
        channel = pick(rng, CHANNELS)
        if rng.randint(1, 100) <= CANCEL_RATE_PCT:
            orders.append(
                Order(order_id, customer.customer_id, order_date.isoformat(), channel,
                      "cancelled", None, None)
            )
            continue
        ship_date = order_date + timedelta(days=rng.randint(*SHIPPING_DAYS))
        delivery_date = ship_date + timedelta(days=rng.randint(*DELIVERY_DAYS[customer.region]))
        orders.append(
            Order(order_id, customer.customer_id, order_date.isoformat(), channel,
                  "delivered", ship_date.isoformat(), delivery_date.isoformat())
        )
    return orders


LINES_PER_ORDER = {1: 50, 2: 30, 3: 15, 4: 5}
QUANTITY = {1: 70, 2: 22, 3: 8}
DISCOUNT_PCT = {0: 80, 10: 15, 20: 5}
NOVEMBER_DISCOUNT_PCT = {0: 40, 10: 30, 20: 30}  # holiday promotion


@dataclass(frozen=True)
class OrderItem:
    order_id: int
    product_id: int
    quantity: int
    unit_price_cents: int
    discount_pct: int


def generate_order_items(
    rng: random.Random, orders: list[Order], products: list[Product]
) -> list[OrderItem]:
    items = []
    for order in orders:
        discounts = NOVEMBER_DISCOUNT_PCT if order.order_date[5:7] == "11" else DISCOUNT_PCT
        for product in rng.sample(products, pick(rng, LINES_PER_ORDER)):
            items.append(
                OrderItem(order.order_id, product.product_id, pick(rng, QUANTITY),
                          product.unit_price_cents, pick(rng, discounts))
            )
    return items


RETURN_REASONS = ("wrong size", "damaged in transit", "not as described", "changed mind")
RETURN_WINDOW_DAYS = (3, 25)


@dataclass(frozen=True)
class Return:
    return_id: int
    order_id: int
    product_id: int
    return_date: str
    quantity: int
    reason: str


def generate_returns(
    rng: random.Random, orders: list[Order], items: list[OrderItem], products: list[Product]
) -> list[Return]:
    """Only delivered lines can be returned; the chance depends on the product category."""
    delivered_on = {o.order_id: o.delivery_date for o in orders if o.status == "delivered"}
    category_of = {p.product_id: p.category for p in products}
    returns = []
    for item in items:
        delivery_date = delivered_on.get(item.order_id)
        if delivery_date is None:
            continue
        if rng.randint(1, 100) > CATEGORIES[category_of[item.product_id]].return_rate_pct:
            continue
        return_date = date.fromisoformat(delivery_date) + timedelta(days=rng.randint(*RETURN_WINDOW_DAYS))
        returns.append(
            Return(len(returns) + 1, item.order_id, item.product_id, return_date.isoformat(),
                   rng.randint(1, item.quantity), rng.choice(RETURN_REASONS))
        )
    return returns


@dataclass(frozen=True)
class Dataset:
    customers: list[Customer]
    products: list[Product]
    orders: list[Order]
    order_items: list[OrderItem]
    returns: list[Return]


# Load order respects foreign keys.
ROW_TYPES = {
    "customers": Customer,
    "products": Product,
    "orders": Order,
    "order_items": OrderItem,
    "returns": Return,
}
TABLES = tuple(ROW_TYPES)


def generate(seed: int = SEED) -> Dataset:
    rng = random.Random(seed)
    customers, activity = generate_customers(rng)
    products = generate_products(rng)
    orders = generate_orders(rng, customers, activity)
    items = generate_order_items(rng, orders, products)
    returns = generate_returns(rng, orders, items, products)
    return Dataset(customers, products, orders, items, returns)


def write_csv(dataset: Dataset, out_dir: Path) -> list[Path]:
    """Write one CSV per table (LF line endings, empty field for NULL)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for table, row_type in ROW_TYPES.items():
        path = out_dir / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow([field.name for field in fields(row_type)])
            writer.writerows(astuple(row) for row in getattr(dataset, table))
        paths.append(path)
    return paths
