"""Shared pytest fixtures.

A fixture is a reusable piece of setup: any test that takes a parameter named `db` gets a fresh,
empty database in a temporary folder, and it's closed again after the test. The real
data/videojoker.db is never touched.
"""

import pytest

from core.database import Database

OWNER_ID = 1000  # a fake Discord user id used as the bot owner in tests


# name="db" lets tests ask for `db`, while the function itself has a different name.
# That keeps pylint from warning that each test's `db` parameter "redefines" this function.
@pytest.fixture(name="db")
async def fixture_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OWNER", str(OWNER_ID))  # Database reads OWNER from the environment
    database = Database(db_path=tmp_path / "test.db")
    await database.setup()
    yield database
    await database.close()
