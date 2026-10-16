import pytest

from result_explainer.db import build_database


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """A fresh database built from the committed sample data."""
    path = tmp_path_factory.mktemp("db") / "store.db"
    build_database(path)
    return path
