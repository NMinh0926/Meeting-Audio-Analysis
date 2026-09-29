"""Pydantic schemas for request/response models."""

from pydantic import BaseModel


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


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class SpeakerSegment(BaseModel):
    speaker: str
    start: float
    end: float


class SpeakerTurn(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


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


class MeetingAnalysisResult(BaseModel):
    filename: str
    duration: float
    speaker_count: int
    segments: list[FinalTurn]

