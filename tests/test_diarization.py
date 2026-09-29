"""Tests for diarization service."""
import pytest

from app.services.diarization import (
    diarize_audio,
    NoSpeakerDetectedError,
    DiarizationError,
    DiarizationAuthError
)

class MockTurn:
    def __init__(self, start, end):
        self.start = start
        self.end = end

class MockDiarizationResult:
    def __init__(self, tracks):
        self._tracks = tracks # list of (turn, None, speaker)
        
    def itertracks(self, yield_label=False):
        return self._tracks

class MockPipeline:
    def __init__(self):
        self.returns = MockDiarizationResult([])
        self.should_raise = False
        
    def __call__(self, audio):
        if self.should_raise:
            raise RuntimeError("Mocked pipeline error")
        return self.returns

@pytest.fixture
def mock_pipeline(monkeypatch):
    pipeline = MockPipeline()
    monkeypatch.setattr("app.services.diarization.get_diarization_pipeline", lambda: pipeline)
    return pipeline

@pytest.fixture
def dummy_audio(tmp_path):
    p = tmp_path / "dummy_diarize.wav"
    p.touch()
    return p

def test_diarize_audio_success(mock_pipeline, dummy_audio):
    tracks = [
        (MockTurn(0.0, 3.0), None, "SPEAKER_00"),
        (MockTurn(3.5, 5.0), None, "SPEAKER_01"),
        (MockTurn(5.0, 6.0), None, "SPEAKER_00"),
    ]
    mock_pipeline.returns = MockDiarizationResult(tracks)
    
    result = diarize_audio(dummy_audio)
    
    assert len(result) == 3
    assert result[0].speaker == "SPEAKER_00"
    assert result[0].start == 0.0
    assert result[0].end == 3.0
    
    assert result[1].speaker == "SPEAKER_01"
    assert result[2].speaker == "SPEAKER_00"
    
    # Check unique speaker count
    speakers = set(s.speaker for s in result)
    assert len(speakers) == 2

def test_diarize_audio_no_speakers(mock_pipeline, dummy_audio):
    mock_pipeline.returns = MockDiarizationResult([])
    
    with pytest.raises(NoSpeakerDetectedError):
        diarize_audio(dummy_audio)

def test_diarize_audio_error(mock_pipeline, dummy_audio):
    mock_pipeline.should_raise = True
    
    with pytest.raises(DiarizationError):
        diarize_audio(dummy_audio)

def test_diarize_audio_file_not_found():
    with pytest.raises(FileNotFoundError):
        diarize_audio("nonexistent.wav")

