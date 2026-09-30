"""Tests for TXT/SRT transcript exports."""
import uuid

import pytest

from app.api.meetings import _content_disposition
from app.db.models import MeetingStatus
from app.services.export import format_clock, format_srt_time

EXPECTED_TXT = """Họp tuần 12.mp3
Thời lượng: 01:02:05
Người nói: Chị Lan, SPEAKER_01

[00:00:00 - 00:00:04] Chị Lan: Chào mọi người. Bắt đầu họp nhé.

[00:00:05 - 00:00:07] SPEAKER_01: Vâng, em báo cáo trước.

[01:01:40 - 01:02:05] Chị Lan: Cảm ơn cả nhà.
"""

EXPECTED_SRT = """1
00:00:00,000 --> 00:00:01,500
Chị Lan: Chào mọi người.

2
00:00:01,800 --> 00:00:04,200
Chị Lan: Bắt đầu họp nhé.

3
00:00:05,000 --> 00:00:07,250
SPEAKER_01: Vâng, em báo cáo trước.

4
01:01:40,000 --> 01:02:05,500
Chị Lan: Cảm ơn cả nhà.
"""


@pytest.mark.parametrize("seconds, clock", [(0, "00:00:00"), (59.99, "00:00:59"), (3725.5, "01:02:05"),
                                            (-1, "00:00:00"), (36000, "10:00:00")])
def test_format_clock(seconds, clock):
    assert format_clock(seconds) == clock


@pytest.mark.parametrize("seconds, stamp", [(0, "00:00:00,000"), (1.5, "00:00:01,500"), (7.2499, "00:00:07,250"),
                                            (59.9996, "00:01:00,000"), (3725.5, "01:02:05,500")])
def test_format_srt_time(seconds, stamp):
    assert format_srt_time(seconds) == stamp


@pytest.fixture
def renamed(client, done_meeting):
    speaker_id = done_meeting.speakers[0].id
    client.patch(f"/api/v1/meetings/{done_meeting.id}/speakers/{speaker_id}", json={"display_name": "Chị Lan"})
    return done_meeting


def test_export_txt_uses_display_names(client, renamed):
    response = client.get(f"/api/v1/meetings/{renamed.id}/export", params={"format": "txt"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == EXPECTED_TXT


def test_export_srt_has_one_cue_per_utterance(client, renamed):
    response = client.get(f"/api/v1/meetings/{renamed.id}/export", params={"format": "srt"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-subrip; charset=utf-8"
    assert response.text == EXPECTED_SRT


def test_export_is_a_download_named_after_the_recording(client, done_meeting):
    response = client.get(f"/api/v1/meetings/{done_meeting.id}/export", params={"format": "srt"})

    assert response.headers["content-disposition"] == (
        "attachment; filename=\"Hop tuan 12.srt\"; filename*=UTF-8''H%E1%BB%8Dp%20tu%E1%BA%A7n%2012.srt")


@pytest.mark.parametrize("filename, fallback", [
    ("Đề xuất đợt 2.txt", "De xuat dot 2.txt"),
    ('a"b\\c\nd.txt', "abcd.txt"),
    ("会议.txt", "transcript.txt"),
    ("会议", "transcript"),
])
def test_content_disposition_ascii_fallback(filename, fallback):
    assert _content_disposition(filename).startswith(f'attachment; filename="{fallback}"; filename*=UTF-8\'\'')


def test_export_rejects_unknown_format(client, done_meeting):
    assert client.get(f"/api/v1/meetings/{done_meeting.id}/export", params={"format": "pdf"}).status_code == 422
    assert client.get(f"/api/v1/meetings/{done_meeting.id}/export").status_code == 422


def test_export_requires_processed_meeting(client, done_meeting, db_session):
    done_meeting.status = MeetingStatus.processing
    db_session.commit()
    assert client.get(f"/api/v1/meetings/{done_meeting.id}/export", params={"format": "txt"}).status_code == 409


def test_export_of_unknown_meeting_is_404(client):
    assert client.get(f"/api/v1/meetings/{uuid.uuid4()}/export", params={"format": "txt"}).status_code == 404
