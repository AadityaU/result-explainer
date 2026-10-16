from datetime import date

import pytest

from result_explainer.generate import SEED, generate, write_csv
from result_explainer.paths import DATA_DIR


@pytest.fixture(scope="module")
def dataset():
    return generate(SEED)


def test_same_seed_produces_identical_files(tmp_path, dataset):
    first = write_csv(dataset, tmp_path / "a")
    second = write_csv(generate(SEED), tmp_path / "b")
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_committed_sample_data_matches_the_generator(tmp_path, dataset):
    for path in write_csv(dataset, tmp_path):
        committed = (DATA_DIR / path.name).read_bytes().replace(b"\r\n", b"\n")
        assert path.read_bytes() == committed, f"{path.name} is stale: run generate-data"


def test_another_seed_produces_different_data(dataset):
    assert generate(SEED + 1).orders != dataset.orders


def test_orders_only_come_from_signed_up_customers(dataset):
    signup = {c.customer_id: c.signup_date for c in dataset.customers}
    assert all(signup[o.customer_id] <= o.order_date for o in dataset.orders)


def test_no_delivery_misses_the_14_day_promise(dataset):
    # q10 is empty by design because of this property.
    for order in dataset.orders:
        if order.status == "delivered":
            days = date.fromisoformat(order.delivery_date) - date.fromisoformat(order.order_date)
            assert days.days <= 14


def test_returns_only_reference_delivered_lines(dataset):
    delivered = {o.order_id for o in dataset.orders if o.status == "delivered"}
    lines = {(i.order_id, i.product_id): i.quantity for i in dataset.order_items}
    for ret in dataset.returns:
        assert ret.order_id in delivered
        assert 1 <= ret.quantity <= lines[(ret.order_id, ret.product_id)]
