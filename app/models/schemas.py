"""Pydantic schemas for request/response models."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db.models import MeetingStatus


class AudioMetadata(BaseModel):
    """Metadata extracted from an audio file."""

    filename: str
    duration_seconds: float
    sample_rate: int
    channels: int


class PreprocessingResult(BaseModel):
    """Result of audio preprocessing."""

    original: AudioMetadata
    normalized: AudioMetadata
    normalized_path: str


class Word(BaseModel):
    start: float
    end: float
    text: str


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    # Word timings from Whisper, used to split a sentence where the speaker changes.
    words: list[Word] = []


class SpeakerSegment(BaseModel):
    speaker: str
    start: float
    end: float


class SpeakerTurn(BaseModel):
    speaker: str
    start: float
    end: float
    text: str
    # Transcript segments (sentences) that make up a merged turn.
    utterances: list[TranscriptSegment] = []


class GenderResult(BaseModel):
    gender: str
    confidence: float


class SentimentResult(BaseModel):
    sentiment: str
    confidence: float


class FinalTurn(BaseModel):
    speaker: str
    gender: str
    gender_confidence: float
    sentiment: str
    sentiment_confidence: float
    start: float
    end: float
    text: str
    utterances: list[TranscriptSegment] = []


class MeetingAnalysisResult(BaseModel):
    filename: str
    duration: float
    speaker_count: int
    segments: list[FinalTurn]



# --- API: /api/v1/meetings

class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    display_name: str
    gender: str
    gender_confidence: float


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: MeetingStatus
    current_stage: str | None
    error_code: str | None
    error_message: str | None
    attempts: int
    duration_seconds: float | None
    speaker_count: int | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MeetingDetail(MeetingOut):
    speakers: list[SpeakerOut]


class MeetingList(BaseModel):
    items: list[MeetingDetail]
    total: int
    limit: int
    offset: int


class SpeakerRename(BaseModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UtteranceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: float
    end: float
    text: str


class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    speaker_id: int
    start: float
    end: float
    text: str
    # Emotion of the turn, one of app.services.emotion_labels.EMOTIONS (field name kept from the first version)
    sentiment: str
    sentiment_confidence: float
    utterances: list[UtteranceOut]


class TranscriptSpeakerOut(SpeakerOut):
    # Emotion filling most of the speaker's talk time, and each emotion's share of it (largest first)
    emotion: str
    emotion_shares: dict[str, float]


class TranscriptOut(BaseModel):
    meeting_id: uuid.UUID
    filename: str
    duration_seconds: float | None
    speakers: list[TranscriptSpeakerOut]
    turns: list[TurnOut]
