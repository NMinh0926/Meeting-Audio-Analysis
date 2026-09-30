"""Tests for gender classification service."""
import pytest
import numpy as np
from unittest.mock import MagicMock

from app.services.gender import predict_speakers_gender, select_chunks
from app.models.schemas import SpeakerSegment

class MockAudioSegment:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms
        
    def __getitem__(self, val):
        return self
        
    def get_array_of_samples(self):
        # return dummy samples
        return [0] * 16000

@pytest.fixture
def mock_gender_pipeline(monkeypatch):
    def mock_classifier(samples):
        # Fake male bias
        return [{"label": "male", "score": 0.8}, {"label": "female", "score": 0.2}]
        
    monkeypatch.setattr("app.services.gender.get_gender_pipeline", lambda: mock_classifier)
    
    # Mock AudioSegment.from_wav
    monkeypatch.setattr("app.services.gender.AudioSegment.from_wav", lambda x: MockAudioSegment(10000))

def test_predict_speakers_gender_success(mock_gender_pipeline):
    segments = [
        SpeakerSegment(speaker="SPK1", start=0.0, end=1.0),
        SpeakerSegment(speaker="SPK1", start=2.0, end=3.0),
        SpeakerSegment(speaker="SPK2", start=4.0, end=5.0)
    ]
    
    result = predict_speakers_gender("dummy.wav", segments)
    
    assert len(result) == 2
    assert result["SPK1"].gender == "male"
    assert result["SPK1"].confidence == 0.8
    assert result["SPK2"].gender == "male"

def test_predict_speakers_gender_skip_short(mock_gender_pipeline, monkeypatch):
    from app.core.config import Settings
    def mock_get_settings():
        s = Settings()
        s.MIN_GENDER_DURATION = 2.0
        return s
        
    monkeypatch.setattr("app.services.gender.get_settings", mock_get_settings)
    
    segments = [
        SpeakerSegment(speaker="SPK1", start=0.0, end=0.5), # Too short
    ]
    
    result = predict_speakers_gender("dummy.wav", segments)
    # Total duration will be 0
    assert result["SPK1"].gender == "unknown"

def test_predict_speakers_gender_empty():
    result = predict_speakers_gender("dummy.wav", [])
    assert result == {}

def test_predict_speakers_gender_model_fail(monkeypatch):
    def mock_fail():
        raise RuntimeError("Model failed")
    monkeypatch.setattr("app.services.gender.get_gender_pipeline", mock_fail)
    
    segments = [SpeakerSegment(speaker="SPK1", start=0.0, end=1.0)]
    result = predict_speakers_gender("dummy.wav", segments)
    
    assert result["SPK1"].gender == "unknown"
    assert result["SPK1"].confidence == 0.0


def _seg(start, end, speaker="S"):
    return SpeakerSegment(speaker=speaker, start=start, end=end)


def test_select_chunks_takes_longest_segments_first_in_bounded_pieces():
    segments = [_seg(0, 3), _seg(10, 35), _seg(40, 48)]

    chunks = select_chunks(segments, min_duration=0.5, chunk_seconds=10, budget_seconds=35)

    assert chunks == [(10, 20), (20, 30), (30, 35), (40, 48), (0, 2)]


def test_select_chunks_skips_pieces_shorter_than_minimum():
    chunks = select_chunks([_seg(0, 10.3), _seg(20, 20.4)], min_duration=0.5, chunk_seconds=5, budget_seconds=60)
    assert chunks == [(0, 5), (5, 10)]


def test_select_chunks_bounds_audio_of_a_long_meeting():
    # 45 minutes of one speaker in 200-second turns: only the budget is classified.
    segments = [_seg(i * 200.0, i * 200.0 + 200.0) for i in range(14)]
    chunks = select_chunks(segments, min_duration=0.5, chunk_seconds=10, budget_seconds=60)
    assert len(chunks) == 6
    assert all(end - start == 10 for start, end in chunks)


def test_low_confidence_speaker_is_unknown(monkeypatch):
    monkeypatch.setattr("app.services.gender.get_gender_pipeline",
                        lambda: lambda samples: [{"label": "male", "score": 0.55}, {"label": "female", "score": 0.45}])
    monkeypatch.setattr("app.services.gender.AudioSegment.from_wav", lambda x: MockAudioSegment(10000))

    result = predict_speakers_gender("dummy.wav", [_seg(0, 2)])

    assert result["S"].gender == "unknown"
    assert result["S"].confidence == 0.55


def test_long_turns_are_classified_in_pieces(monkeypatch):
    lengths = []

    class RecordingAudio(MockAudioSegment):
        def __getitem__(self, val):
            lengths.append(val.stop - val.start)
            return self

    monkeypatch.setattr("app.services.gender.get_gender_pipeline",
                        lambda: lambda samples: [{"label": "female", "score": 0.9}, {"label": "male", "score": 0.1}])
    monkeypatch.setattr("app.services.gender.AudioSegment.from_wav", lambda x: RecordingAudio(300000))

    result = predict_speakers_gender("dummy.wav", [_seg(0, 222.8)])

    assert result["S"].gender == "female"
    assert lengths == [10000] * 6
