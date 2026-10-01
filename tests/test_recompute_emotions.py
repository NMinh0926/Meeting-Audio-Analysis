"""Tests for scripts.recompute_emotions with fake models and in-memory storage."""
from pathlib import Path

import pytest

from app.models.schemas import AudioMetadata, PreprocessingResult, SentimentResult
from scripts.recompute_emotions import recompute_meeting


def _preprocess(tmp_path: Path, seen: list[bytes]):
    def preprocess(original: Path) -> PreprocessingResult:
        seen.append(original.read_bytes())
        normalized = tmp_path / "normalized.wav"
        normalized.write_bytes(b"wav")
        meta = AudioMetadata(filename=original.name, duration_seconds=1.0, sample_rate=16000, channels=1)
        return PreprocessingResult(original=meta, normalized=meta, normalized_path=str(normalized))
    return preprocess


def test_recompute_updates_each_turn_and_keeps_the_transcript(db_session, storage, done_meeting, tmp_path):
    downloaded: list[bytes] = []
    calls = []

    def predict(path, turns):
        calls.append((Path(path).exists(), [(t.start, t.text, [u.text for u in t.utterances]) for t in turns]))
        return [SentimentResult(sentiment=e, confidence=c) for e, c in (("sad", 0.6), ("happy", 0.7), ("angry", 0.8))]

    changed = recompute_meeting(db_session, storage, done_meeting, tmp_path, predict, _preprocess(tmp_path, downloaded))

    assert downloaded == [storage.objects[done_meeting.storage_key][0]]
    assert calls == [(True, [
        (0.0, "Chào mọi người. Bắt đầu họp nhé.", ["Chào mọi người.", "Bắt đầu họp nhé."]),
        (5.0, "Vâng, em báo cáo trước.", ["Vâng, em báo cáo trước."]),
        (3700.0, "Cảm ơn cả nhà.", ["Cảm ơn cả nhà."]),
    ])]
    assert changed == 2  # the second turn was already happy
    db_session.expire_all()
    assert [(s.sentiment, s.sentiment_confidence, s.text) for s in done_meeting.segments] == [
        ("sad", 0.6, "Chào mọi người. Bắt đầu họp nhé."),
        ("happy", 0.7, "Vâng, em báo cáo trước."),
        ("angry", 0.8, "Cảm ơn cả nhà."),
    ]
    assert not (tmp_path / "normalized.wav").exists()
    assert [p.name for p in tmp_path.iterdir()] == []


def test_recompute_removes_the_normalized_audio_when_the_model_fails(db_session, storage, done_meeting, tmp_path):
    def predict(path, turns):
        raise RuntimeError("CUDA out of memory")

    with pytest.raises(RuntimeError):
        recompute_meeting(db_session, storage, done_meeting, tmp_path, predict, _preprocess(tmp_path, []))

    assert list(tmp_path.iterdir()) == []
    db_session.expire_all()
    assert [s.sentiment for s in done_meeting.segments] == ["neutral", "happy", "happy"]
