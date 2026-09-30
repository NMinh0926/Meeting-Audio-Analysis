"""Tests for /api/v1/meetings (PostgreSQL test database, in-memory storage)."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.meetings import get_storage
from app.db.models import Meeting, MeetingStatus, Segment, Speaker
from app.db.session import get_db
from app.main import app
from tests.fakes import InMemoryStorage


@pytest.fixture
def client(sessions, storage):
    def db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def _files(*names: str, content: bytes = b"RIFF-audio") -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, content, "application/octet-stream")) for name in names]


def _meeting(db_session, status: MeetingStatus, filename: str = "a.wav") -> Meeting:
    meeting_id = uuid.uuid4()
    meeting = Meeting(id=meeting_id, filename=filename, content_type="audio/wav", size_bytes=3,
                      storage_key=f"meetings/{meeting_id}/original.wav", status=status)
    db_session.add(meeting)
    db_session.commit()
    return meeting


def test_upload_several_files_queues_one_meeting_each(client, storage, db_session):
    response = client.post("/api/v1/meetings", files=_files("a.wav", "b.MP3", "c.m4a"))

    assert response.status_code == 202
    body = response.json()
    assert [m["filename"] for m in body] == ["a.wav", "b.MP3", "c.m4a"]
    assert {m["status"] for m in body} == {"queued"}
    assert [m["content_type"] for m in body] == ["audio/wav", "audio/mpeg", "audio/mp4"]
    assert db_session.scalar(select(func.count()).select_from(Meeting)) == 3
    keys = db_session.scalars(select(Meeting.storage_key)).all()
    assert set(keys) == set(storage.objects)
    assert all(storage.objects[key][0] == b"RIFF-audio" for key in keys)
    assert any(key.endswith("/original.mp3") for key in keys)


def test_upload_keeps_only_base_filename(client):
    response = client.post("/api/v1/meetings", files=_files("../../etc/meeting.wav"))
    assert response.status_code == 202
    assert response.json()[0]["filename"] == "meeting.wav"


@pytest.mark.parametrize(
    "files, message",
    [
        (_files("notes.txt"), "unsupported format"),
        (_files("empty.wav", content=b""), "empty"),
    ],
)
def test_invalid_upload_is_rejected_without_storing_anything(client, storage, db_session, files, message):
    response = client.post("/api/v1/meetings", files=_files("ok.wav") + files)

    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert storage.objects == {}
    assert db_session.scalar(select(func.count()).select_from(Meeting)) == 0


def test_upload_over_size_limit_is_rejected(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_MB", 1)
    response = client.post("/api/v1/meetings", files=_files("big.wav", content=b"x" * (1024 * 1024 + 1)))
    assert response.status_code == 400
    assert "exceeds 1 MB" in response.json()["detail"]


def test_upload_without_files_is_rejected(client):
    assert client.post("/api/v1/meetings").status_code == 422


def test_storage_failure_removes_uploaded_objects(client, db_session):
    failing = InMemoryStorage(fail_uploads_after=1)
    app.dependency_overrides[get_storage] = lambda: failing

    response = client.post("/api/v1/meetings", files=_files("a.wav", "b.wav"))

    assert response.status_code == 503
    assert failing.objects == {}
    assert db_session.scalar(select(func.count()).select_from(Meeting)) == 0


def test_list_is_newest_first_with_status_filter_and_paging(client):
    for name in ("1.wav", "2.wav", "3.wav"):
        assert client.post("/api/v1/meetings", files=_files(name)).status_code == 202

    body = client.get("/api/v1/meetings").json()
    assert body["total"] == 3
    assert [m["filename"] for m in body["items"]] == ["3.wav", "2.wav", "1.wav"]

    page = client.get("/api/v1/meetings", params={"limit": 1, "offset": 1}).json()
    assert [m["filename"] for m in page["items"]] == ["2.wav"]
    assert page["total"] == 3

    assert client.get("/api/v1/meetings", params={"status": "done"}).json()["total"] == 0
    assert client.get("/api/v1/meetings", params={"status": "queued"}).json()["total"] == 3
    assert client.get("/api/v1/meetings", params={"status": "bogus"}).status_code == 422


def test_detail_includes_speakers(client, db_session):
    meeting = _meeting(db_session, MeetingStatus.done)
    speaker = Speaker(label="SPEAKER_00", display_name="SPEAKER_00", gender="female", gender_confidence=0.9)
    meeting.speakers.append(speaker)
    meeting.segments.append(Segment(speaker=speaker, start=0.0, end=1.0, text="Xin chào",
                                    sentiment="neutral", sentiment_confidence=0.5))
    db_session.commit()

    body = client.get(f"/api/v1/meetings/{meeting.id}").json()

    assert body["status"] == "done"
    assert body["speakers"] == [
        {"id": speaker.id, "label": "SPEAKER_00", "display_name": "SPEAKER_00",
         "gender": "female", "gender_confidence": 0.9}
    ]


def test_unknown_meeting_returns_404(client):
    missing = uuid.uuid4()
    assert client.get(f"/api/v1/meetings/{missing}").status_code == 404
    assert client.post(f"/api/v1/meetings/{missing}/retry").status_code == 404
    assert client.delete(f"/api/v1/meetings/{missing}").status_code == 404
    assert client.get("/api/v1/meetings/not-a-uuid").status_code == 422


def test_retry_requeues_failed_meeting(client, db_session):
    meeting = _meeting(db_session, MeetingStatus.failed)
    meeting.error_code, meeting.error_message = "DiarizationError", "boom"
    db_session.commit()

    response = client.post(f"/api/v1/meetings/{meeting.id}/retry")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["error_code"] is None and body["error_message"] is None


@pytest.mark.parametrize("state", [MeetingStatus.queued, MeetingStatus.processing, MeetingStatus.done])
def test_retry_only_allowed_for_failed(client, db_session, state):
    meeting = _meeting(db_session, state)
    response = client.post(f"/api/v1/meetings/{meeting.id}/retry")
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(Meeting, meeting.id).status == state


def test_delete_removes_rows_and_recording(client, storage, db_session):
    meeting_id = client.post("/api/v1/meetings", files=_files("a.wav")).json()[0]["id"]
    meeting = db_session.get(Meeting, uuid.UUID(meeting_id))
    speaker = Speaker(label="SPEAKER_00", display_name="SPEAKER_00", gender="male", gender_confidence=0.8)
    meeting.speakers.append(speaker)
    meeting.segments.append(Segment(speaker=speaker, start=0, end=1, text="a", sentiment="neutral",
                                    sentiment_confidence=0.5))
    db_session.commit()

    assert client.delete(f"/api/v1/meetings/{meeting_id}").status_code == 204

    db_session.expire_all()
    assert db_session.get(Meeting, uuid.UUID(meeting_id)) is None
    assert db_session.scalar(select(func.count()).select_from(Segment)) == 0
    assert db_session.scalar(select(func.count()).select_from(Speaker)) == 0
    assert storage.objects == {}


def test_delete_processing_meeting_is_refused(client, db_session):
    meeting = _meeting(db_session, MeetingStatus.processing)
    assert client.delete(f"/api/v1/meetings/{meeting.id}").status_code == 409
    db_session.expire_all()
    assert db_session.get(Meeting, meeting.id) is not None


def test_list_keeps_upload_order_within_one_request(client):
    client.post("/api/v1/meetings", files=_files(*[f"{i}.wav" for i in range(10)]))
    names = [m["filename"] for m in client.get("/api/v1/meetings").json()["items"]]
    assert names == [f"{i}.wav" for i in reversed(range(10))]
