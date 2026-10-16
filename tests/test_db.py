import sqlite3

import pytest

from result_explainer.db import build_database, connect_read_only
from result_explainer.generate import TABLES
from result_explainer.paths import DATA_DIR


def test_build_loads_every_csv_row(tmp_path):
    counts = build_database(tmp_path / "store.db")
    for table in TABLES:
        with (DATA_DIR / f"{table}.csv").open(encoding="utf-8") as handle:
            assert counts[table] == sum(1 for _ in handle) - 1


def test_loaded_data_respects_foreign_keys(db_path):
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_empty_csv_fields_become_null(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT typeof(ship_date), typeof(delivery_date) FROM orders"
            " WHERE status = 'cancelled'"
        ).fetchall()
    assert rows == [("null", "null")]


def test_read_only_connection_rejects_writes(db_path):
    conn = connect_read_only(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM orders")
    finally:
        conn.close()


def test_missing_database_explains_how_to_build_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="build-db"):
        connect_read_only(tmp_path / "missing.db")
