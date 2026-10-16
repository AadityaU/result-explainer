"""Build the SQLite database from the schema and the CSV sample data."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from result_explainer.generate import TABLES
from result_explainer.paths import DATA_DIR, DEFAULT_DB, SCHEMA_PATH


def build_database(
    db_path: Path = DEFAULT_DB, data_dir: Path = DATA_DIR, schema_path: Path = SCHEMA_PATH
) -> dict[str, int]:
    """Recreate the database from scratch and load every CSV. Returns rows loaded per table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        counts = {table: _load_csv(conn, table, data_dir / f"{table}.csv") for table in TABLES}
        conn.commit()
    finally:
        conn.close()
    return counts


def _load_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [[value if value != "" else None for value in row] for row in reader]
    columns = ", ".join(header)
    placeholders = ", ".join("?" for _ in header)
    conn.executemany(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", rows)
    return len(rows)
