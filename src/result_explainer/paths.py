"""Repository locations. The package runs from a source checkout (pip install -e .)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
SCHEMA_PATH = SQL_DIR / "schema.sql"
QUESTIONS_DIR = SQL_DIR / "questions"
DATA_DIR = ROOT / "data"
DEFAULT_DB = ROOT / "build" / "store.db"
