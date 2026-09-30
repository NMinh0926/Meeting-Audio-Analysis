"""Tests for full pipeline."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.models.schemas import (
    MeetingAnalysisResult, 
    TranscriptSegment, 
    SpeakerSegment, 
    GenderResult, 
    SentimentResult,
    PreprocessingResult,
    AudioMetadata
)
from app.services.pipeline import analyze_meeting

@pytest.fixture
def mock_all_services(monkeypatch):
    def mock_preprocess(path):
        return PreprocessingResult(
            original=AudioMetadata(filename="dummy.wav", duration_seconds=10.0, sample_rate=44100, channels=2),
            normalized=AudioMetadata(filename="dummy_norm.wav", duration_seconds=10.0, sample_rate=16000, channels=1),
            normalized_path="data/temp/dummy_norm.wav"
        )
        
    def mock_transcribe(path):
        return [
            TranscriptSegment(start=0.5, end=2.5, text="Xin chào."),
            TranscriptSegment(start=3.0, end=4.5, text="Chào bạn.")
        ]
        
    def mock_diarize(path):
        return [
            SpeakerSegment(speaker="SPK_0", start=0.0, end=2.8),
            SpeakerSegment(speaker="SPK_1", start=2.9, end=5.0)
        ]
        
    def mock_gender(path, speakers):
        return {
            "SPK_0": GenderResult(gender="male", confidence=0.9),
            "SPK_1": GenderResult(gender="female", confidence=0.85)
        }
        
    def mock_sentiment(text):
        if "Xin chào" in text:
            return SentimentResult(sentiment="happy", confidence=0.99)
        return SentimentResult(sentiment="neutral", confidence=0.5)

    monkeypatch.setattr("app.services.pipeline.preprocess_audio", mock_preprocess)
    monkeypatch.setattr("app.services.pipeline.transcribe_audio", mock_transcribe)
    monkeypatch.setattr("app.services.pipeline.diarize_audio", mock_diarize)
    # Using real align and merge
    monkeypatch.setattr("app.services.pipeline.predict_speakers_gender", mock_gender)
    monkeypatch.setattr("app.services.pipeline.predict_sentiment", mock_sentiment)

def test_analyze_meeting_full(mock_all_services, tmp_path):
    dummy = tmp_path / "dummy.wav"
    dummy.touch()
    
    res = analyze_meeting(dummy)
    
    assert isinstance(res, MeetingAnalysisResult)
    assert res.speaker_count == 2
    assert len(res.segments) == 2
    
    seg0 = res.segments[0]
    assert seg0.speaker == "SPK_0"
    assert seg0.gender == "male"
    assert seg0.sentiment == "happy"
    assert seg0.text == "Xin chào."
    
    seg1 = res.segments[1]
    assert seg1.speaker == "SPK_1"
    assert seg1.gender == "female"
    assert seg1.sentiment == "neutral"
    assert seg1.text == "Chào bạn."
    assert [(u.start, u.end, u.text) for u in seg0.utterances] == [(0.5, 2.5, "Xin chào.")]
    assert [(u.start, u.end, u.text) for u in seg1.utterances] == [(3.0, 4.5, "Chào bạn.")]

def test_analyze_meeting_gender_fail(mock_all_services, monkeypatch, tmp_path):
    def mock_gender_empty(path, speakers):
        return {} # simulate failure
    monkeypatch.setattr("app.services.pipeline.predict_speakers_gender", mock_gender_empty)
    
    dummy = tmp_path / "dummy.wav"
    dummy.touch()
    
    res = analyze_meeting(dummy)
    assert res.segments[0].gender == "unknown"
    assert res.segments[1].gender == "unknown"
    assert res.segments[0].text == "Xin chào." # still preserves transcript



def test_analyze_meeting_reports_stages_in_order(mock_all_services, tmp_path):
    dummy = tmp_path / "dummy.wav"
    dummy.touch()
    stages = []

    analyze_meeting(dummy, on_stage=stages.append)

    assert stages == ["preprocessing", "transcription", "diarization", "alignment",
                      "merging", "gender", "sentiment"]


def _normalized_file(monkeypatch, tmp_path) -> Path:
    normalized = tmp_path / "normalized.wav"
    normalized.write_bytes(b"wav")
    monkeypatch.setattr("app.services.pipeline.preprocess_audio", lambda path: PreprocessingResult(
        original=AudioMetadata(filename="dummy.wav", duration_seconds=10.0, sample_rate=44100, channels=2),
        normalized=AudioMetadata(filename="normalized.wav", duration_seconds=10.0, sample_rate=16000, channels=1),
        normalized_path=str(normalized),
    ))
    return normalized


def test_analyze_meeting_removes_normalized_audio(mock_all_services, monkeypatch, tmp_path):
    normalized = _normalized_file(monkeypatch, tmp_path)

    analyze_meeting(tmp_path / "dummy.wav")

    assert not normalized.exists()


def test_analyze_meeting_removes_normalized_audio_on_failure(mock_all_services, monkeypatch, tmp_path):
    normalized = _normalized_file(monkeypatch, tmp_path)

    def fail(path):
        raise RuntimeError("diarization failed")
    monkeypatch.setattr("app.services.pipeline.diarize_audio", fail)

    with pytest.raises(RuntimeError):
        analyze_meeting(tmp_path / "dummy.wav")
    assert not normalized.exists()


def test_gpu_cache_is_released_before_transcription_and_after_torch_stages(mock_all_services, monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr("app.services.pipeline.release_cached_memory", lambda: events.append("release"))

    analyze_meeting(tmp_path / "dummy.wav", on_stage=events.append)

    assert events[:3] == ["preprocessing", "transcription", "release"]
    assert events[events.index("diarization") + 1] == "release"
    assert events[events.index("gender") + 1] == "release"
