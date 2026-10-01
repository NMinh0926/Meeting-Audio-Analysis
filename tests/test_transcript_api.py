"""Tests for transcript review and speaker renaming."""
import uuid

import pytest

from app.db.models import Meeting, MeetingStatus, Speaker


def test_transcript_lists_speakers_and_turns_with_utterances(client, done_meeting):
    body = client.get(f"/api/v1/meetings/{done_meeting.id}/transcript").json()

    assert body["meeting_id"] == str(done_meeting.id)
    assert body["filename"] == "Họp tuần 12.mp3"
    assert body["duration_seconds"] == 3725.5
    lan, minh = done_meeting.speakers
    assert [(s["id"], s["label"]) for s in body["speakers"]] == [(lan.id, "SPEAKER_00"), (minh.id, "SPEAKER_01")]
    assert [(t["speaker_id"], t["start"], t["sentiment"]) for t in body["turns"]] == [
        (lan.id, 0.0, "neutral"), (minh.id, 5.0, "happy"), (lan.id, 3700.0, "happy")]
    assert body["turns"][0]["utterances"] == [
        {"start": 0.0, "end": 1.5, "text": "Chào mọi người."},
        {"start": 1.8, "end": 4.2, "text": "Bắt đầu họp nhé."},
    ]


@pytest.mark.parametrize("state", [MeetingStatus.queued, MeetingStatus.processing, MeetingStatus.failed])
def test_transcript_requires_processed_meeting(client, done_meeting, db_session, state):
    done_meeting.status = state
    db_session.commit()

    response = client.get(f"/api/v1/meetings/{done_meeting.id}/transcript")

    assert response.status_code == 409
    assert state.value in response.json()["detail"]


def test_transcript_of_unknown_meeting_is_404(client):
    assert client.get(f"/api/v1/meetings/{uuid.uuid4()}/transcript").status_code == 404


def test_rename_speaker_trims_and_shows_in_transcript(client, done_meeting):
    speaker_id = done_meeting.speakers[0].id

    response = client.patch(f"/api/v1/meetings/{done_meeting.id}/speakers/{speaker_id}",
                            json={"display_name": "  Chị Lan  "})

    assert response.status_code == 200
    assert response.json()["display_name"] == "Chị Lan"
    assert response.json()["label"] == "SPEAKER_00"
    speakers = client.get(f"/api/v1/meetings/{done_meeting.id}/transcript").json()["speakers"]
    assert speakers[0]["display_name"] == "Chị Lan"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_rename_rejects_blank_or_long_names(client, done_meeting, name):
    speaker_id = done_meeting.speakers[0].id
    response = client.patch(f"/api/v1/meetings/{done_meeting.id}/speakers/{speaker_id}", json={"display_name": name})
    assert response.status_code == 422


def test_rename_speaker_of_another_meeting_is_404(client, done_meeting, db_session):
    other = Meeting(id=uuid.uuid4(), filename="b.wav", content_type="audio/wav", size_bytes=1,
                    storage_key="meetings/other/original.wav", status=MeetingStatus.done)
    other.speakers.append(Speaker(label="SPEAKER_00", display_name="SPEAKER_00", gender="male",
                                  gender_confidence=0.5))
    db_session.add(other)
    db_session.commit()

    response = client.patch(f"/api/v1/meetings/{done_meeting.id}/speakers/{other.speakers[0].id}",
                            json={"display_name": "Nope"})

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(Speaker, other.speakers[0].id).display_name == "SPEAKER_00"


def test_list_includes_speakers_with_genders(client, done_meeting):
    client.post("/api/v1/meetings", files={"files": ("new.wav", b"RIFF" + b"\0" * 64, "audio/wav")})

    items = client.get("/api/v1/meetings").json()["items"]

    assert [m["filename"] for m in items] == ["new.wav", "Họp tuần 12.mp3"]
    assert items[0]["speakers"] == []
    assert [(s["label"], s["gender"]) for s in items[1]["speakers"]] == [("SPEAKER_00", "female"),
                                                                        ("SPEAKER_01", "male")]


def test_transcript_speakers_carry_their_overall_emotion(client, done_meeting):
    speakers = client.get(f"/api/v1/meetings/{done_meeting.id}/transcript").json()["speakers"]

    # Lan: 4.2 s neutral, 25.5 s happy; Minh: one happy turn
    assert [(s["emotion"], s["emotion_shares"]) for s in speakers] == [
        ("happy", {"happy": 0.8586, "neutral": 0.1414}),
        ("happy", {"happy": 1.0}),
    ]
