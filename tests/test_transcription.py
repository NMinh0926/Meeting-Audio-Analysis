"""Tests for transcription service."""
from types import SimpleNamespace

import pytest

from app.services.transcription import (
    NoSpeechDetectedError,
    TranscriptionError,
    transcribe_audio,
)


class MockWhisperModel:
    def __init__(self):
        self.segments = []
        self.should_raise = False
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        if self.should_raise:
            raise RuntimeError("Mocked whisper error")
        # faster-whisper returns a lazy generator plus info
        return (s for s in self.segments), SimpleNamespace(language="vi")


def _seg(start, end, text, words=None):
    return SimpleNamespace(start=start, end=end, text=text, words=words)


@pytest.fixture
def mock_model(monkeypatch):
    model = MockWhisperModel()
    monkeypatch.setattr("app.services.transcription.get_whisper_model", lambda: model)
    return model


@pytest.fixture
def dummy_audio(tmp_path):
    p = tmp_path / "dummy_transcribe.wav"
    p.touch()
    return p


def test_transcribe_success(mock_model, dummy_audio):
    mock_model.segments = [
        _seg(0.0, 2.0, " Xin chào mọi người. "),
        _seg(2.0, 4.5, "Hôm nay chúng ta họp."),
    ]

    result = transcribe_audio(dummy_audio)

    assert len(result) == 2
    assert result[0].text == "Xin chào mọi người."
    assert result[1].start == 2.0
    assert result[1].end == 4.5


def test_transcribe_uses_configured_language(mock_model, dummy_audio):
    mock_model.segments = [_seg(0.0, 1.0, "A")]

    transcribe_audio(dummy_audio)

    _, kwargs = mock_model.calls[0]
    assert kwargs["language"] == "vi"


def test_transcribe_skips_blank_segments(mock_model, dummy_audio):
    mock_model.segments = [
        _seg(0.0, 1.0, "   "),
        _seg(1.0, 2.0, "Có nội dung"),
    ]

    result = transcribe_audio(dummy_audio)

    assert [s.text for s in result] == ["Có nội dung"]


def test_transcribe_no_speech(mock_model, dummy_audio):
    mock_model.segments = [_seg(0.0, 1.0, "")]

    with pytest.raises(NoSpeechDetectedError):
        transcribe_audio(dummy_audio)


def test_transcribe_model_error(mock_model, dummy_audio):
    mock_model.should_raise = True

    with pytest.raises(TranscriptionError):
        transcribe_audio(dummy_audio)


def test_transcribe_file_not_found():
    with pytest.raises(FileNotFoundError):
        transcribe_audio("nonexistent.wav")


def test_transcribe_requests_vad_and_word_timestamps(mock_model, dummy_audio, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "WHISPER_VAD", True)
    mock_model.segments = [_seg(0.0, 1.0, "A")]

    transcribe_audio(dummy_audio)

    _, kwargs = mock_model.calls[0]
    assert kwargs["vad_filter"] is True
    assert kwargs["word_timestamps"] is True


def test_transcribe_keeps_word_timings(mock_model, dummy_audio):
    words = [SimpleNamespace(start=0.0, end=0.4, word=" Xin"), SimpleNamespace(start=0.4, end=0.9, word=" chào.")]
    mock_model.segments = [_seg(0.0, 0.9, " Xin chào.", words), _seg(1.0, 2.0, "Không có từ")]

    result = transcribe_audio(dummy_audio)

    assert [(w.start, w.end, w.text) for w in result[0].words] == [(0.0, 0.4, " Xin"), (0.4, 0.9, " chào.")]
    assert result[1].words == []
