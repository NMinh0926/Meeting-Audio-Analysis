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


@pytest.fixture
def client(sessions, storage):
    """API client on the test database and in-memory storage."""
    from fastapi.testclient import TestClient

    from app.api.meetings import get_storage
    from app.db.session import get_db
    from app.main import app

    def db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


AUDIO_BYTES = bytes(range(256)) * 4


@pytest.fixture
def done_meeting(db_session, storage):
    """A processed meeting: 1024-byte recording, two speakers, three turns with utterances."""
    import uuid

    from app.db.models import Meeting, MeetingStatus, Segment, Speaker, Utterance

    meeting_id = uuid.uuid4()
    meeting = Meeting(id=meeting_id, filename="Họp tuần 12.mp3", content_type="audio/mpeg",
                      size_bytes=len(AUDIO_BYTES), storage_key=f"meetings/{meeting_id}/original.mp3",
                      status=MeetingStatus.done, duration_seconds=3725.5, speaker_count=2)
    storage.objects[meeting.storage_key] = (AUDIO_BYTES, "audio/mpeg")
    lan = Speaker(label="SPEAKER_00", display_name="SPEAKER_00", gender="female", gender_confidence=0.9)
    minh = Speaker(label="SPEAKER_01", display_name="SPEAKER_01", gender="male", gender_confidence=0.8)
    meeting.speakers.extend([lan, minh])
    meeting.segments.extend([
        Segment(speaker=lan, start=0.0, end=4.2, text="Chào mọi người. Bắt đầu họp nhé.",
                sentiment="neutral", sentiment_confidence=0.7,
                utterances=[Utterance(start=0.0, end=1.5, text="Chào mọi người."),
                            Utterance(start=1.8, end=4.2, text="Bắt đầu họp nhé.")]),
        Segment(speaker=minh, start=5.0, end=7.25, text="Vâng, em báo cáo trước.",
                sentiment="happy", sentiment_confidence=0.6,
                utterances=[Utterance(start=5.0, end=7.25, text="Vâng, em báo cáo trước.")]),
        Segment(speaker=lan, start=3700.0, end=3725.5, text="Cảm ơn cả nhà.",
                sentiment="happy", sentiment_confidence=0.9,
                utterances=[Utterance(start=3700.0, end=3725.5, text="Cảm ơn cả nhà.")]),
    ])
    db_session.add(meeting)
    db_session.commit()
    return meeting
