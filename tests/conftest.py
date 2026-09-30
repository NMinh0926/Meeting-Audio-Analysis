"""Shared fixtures: the PostgreSQL test database and in-memory storage."""
import os

import pytest

from tests.fakes import InMemoryStorage


def _test_database_url() -> str:
    """TEST_DATABASE_URL, or DATABASE_URL with `_test` appended to the database name (created by initdb)."""
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings

    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    url = make_url(get_settings().DATABASE_URL)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def db_engine():
    """The test database migrated with Alembic (which also checks that the migrations apply)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    url = _test_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL test database unavailable ({type(exc).__name__}); start it with docker compose")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(db_engine):
    """A session factory on an emptied test database."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    with db_engine.begin() as connection:
        connection.execute(text("TRUNCATE meetings CASCADE"))
    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
def db_session(sessions):
    with sessions() as session:
        yield session


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()
