"""Tests for gender classification service."""
import pytest
import numpy as np
from unittest.mock import MagicMock

from app.services.gender import predict_speakers_gender
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
