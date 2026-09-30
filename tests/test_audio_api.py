"""Tests for Range parsing and the audio endpoint."""
import uuid

import pytest

from app.api.byte_range import RangeNotSatisfiableError, parse_range
from tests.conftest import AUDIO_BYTES

SIZE = 1000


@pytest.mark.parametrize(
    "header, expected",
    [
        (None, None),
        ("", None),
        ("bytes=0-99", (0, 99)),
        ("bytes=500-", (500, 999)),
        ("bytes=-100", (900, 999)),
        ("bytes=-5000", (0, 999)),         # suffix longer than the file: whole file
        ("bytes=900-5000", (900, 999)),    # end past the file is clipped
        ("BYTES = 0-0", (0, 0)),
        ("bytes=0-1,5-6", None),           # several ranges: not supported, send everything
        ("items=0-10", None),              # other unit
        ("bytes=abc", None),               # malformed
        ("bytes=5-2", None),               # end before start
        ("bytes=+5-10", None),
        ("bytes=--5", None),
    ],
)
def test_parse_range(header, expected):
    assert parse_range(header, SIZE) == expected


@pytest.mark.parametrize("header", ["bytes=1000-", "bytes=5000-6000", "bytes=-0"])
def test_unsatisfiable_range(header):
    with pytest.raises(RangeNotSatisfiableError):
        parse_range(header, SIZE)


def _audio(client, meeting_id, range_header: str | None = None):
    headers = {"Range": range_header} if range_header else {}
    return client.get(f"/api/v1/meetings/{meeting_id}/audio", headers=headers)


def test_audio_without_range_returns_whole_file(client, done_meeting):
    response = _audio(client, done_meeting.id)

    assert response.status_code == 200
    assert response.content == AUDIO_BYTES
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "1024"
    assert "content-range" not in response.headers


@pytest.mark.parametrize(
    "header, start, end",
    [("bytes=0-99", 0, 99), ("bytes=1000-", 1000, 1023), ("bytes=-24", 1000, 1023), ("bytes=10-10", 10, 10)],
)
def test_audio_range_returns_partial_content(client, done_meeting, header, start, end):
    response = _audio(client, done_meeting.id, header)

    assert response.status_code == 206
    assert response.content == AUDIO_BYTES[start:end + 1]
    assert response.headers["content-range"] == f"bytes {start}-{end}/1024"
    assert response.headers["content-length"] == str(end - start + 1)


def test_audio_range_past_end_is_416(client, done_meeting):
    response = _audio(client, done_meeting.id, "bytes=2048-")

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */1024"


def test_audio_is_available_before_processing_finishes(client, done_meeting, db_session):
    from app.db.models import MeetingStatus

    done_meeting.status = MeetingStatus.queued
    db_session.commit()
    assert _audio(client, done_meeting.id, "bytes=0-9").status_code == 206


def test_audio_of_unknown_meeting_is_404(client):
    assert _audio(client, uuid.uuid4()).status_code == 404


def test_audio_missing_from_storage_is_404(client, done_meeting, storage):
    storage.objects.clear()
    assert _audio(client, done_meeting.id).status_code == 404
