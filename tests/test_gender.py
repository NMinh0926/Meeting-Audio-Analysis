"""Tests for gender classification service (model mocked)."""
import pytest

from app.models.schemas import SpeakerSegment
from app.services.gender import decide_gender, predict_speakers_gender, select_chunks


class MockAudioSegment:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms

    def __getitem__(self, val):
        return self

    def get_array_of_samples(self):
        return [0] * 16000


def _seg(start, end, speaker="S"):
    return SpeakerSegment(speaker=speaker, start=start, end=end)


@pytest.fixture
def mock_model(monkeypatch):
    """Model loads fine; each speaker's male probability comes from `probabilities` (default 0.9)."""
    probabilities: list[float] = []
    monkeypatch.setattr("app.services.gender.get_gender_model", lambda: object())
    monkeypatch.setattr("app.services.gender.AudioSegment.from_wav", lambda x: MockAudioSegment(10000))
    monkeypatch.setattr("app.services.gender.male_probability",
                        lambda samples: probabilities.pop(0) if probabilities else 0.9)
    return probabilities


def test_predict_speakers_gender_per_speaker(mock_model):
    mock_model.extend([0.9, 0.8, 0.02])  # SPK1: two pieces, SPK2: one
    segments = [_seg(0.0, 1.0, "SPK1"), _seg(2.0, 3.0, "SPK1"), _seg(4.0, 5.0, "SPK2")]

    result = predict_speakers_gender("dummy.wav", segments)

    assert result["SPK1"].gender == "male"
    assert result["SPK2"].gender == "female"


def test_speaker_with_only_too_short_segments_is_unknown(mock_model, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MIN_GENDER_DURATION", 2.0)

    result = predict_speakers_gender("dummy.wav", [_seg(0.0, 0.5, "SPK1")])

    assert result["SPK1"].gender == "unknown"
    assert result["SPK1"].confidence == 0.0


def test_predict_speakers_gender_empty():
    assert predict_speakers_gender("dummy.wav", []) == {}


def test_model_load_failure_gives_unknown(monkeypatch):
    def fail():
        raise RuntimeError("Model failed")

    monkeypatch.setattr("app.services.gender.get_gender_model", fail)

    result = predict_speakers_gender("dummy.wav", [_seg(0.0, 1.0, "SPK1")])

    assert result["SPK1"].gender == "unknown"
    assert result["SPK1"].confidence == 0.0


def test_failing_piece_is_skipped(mock_model, monkeypatch):
    calls = []

    def flaky(samples):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("CUDA hiccup")
        return 0.05

    monkeypatch.setattr("app.services.gender.male_probability", flaky)

    result = predict_speakers_gender("dummy.wav", [_seg(0, 10), _seg(20, 25)])

    assert result["S"].gender == "female"
    assert len(calls) == 2


def test_speaker_probability_is_duration_weighted(mock_model):
    # 10 s at 0.1 (female side) and 2 s at 0.9: weighted 0.233 is just above the 0.2 threshold.
    mock_model.extend([0.1, 0.9])

    result = predict_speakers_gender("dummy.wav", [_seg(0, 10), _seg(20, 22)])

    assert result["S"].gender == "unknown"  # confidence 0.52, too close to call
    assert result["S"].confidence == pytest.approx(0.5208, abs=1e-4)


@pytest.mark.parametrize(
    "p_male, gender, confidence",
    [
        (1.0, "male", 1.0),
        (0.6, "male", 0.75),
        (0.35, "male", 0.5938),   # a Vietnamese man the model under-rates
        (0.25, "unknown", 0.5312),
        (0.2, "unknown", 0.5),
        (0.15, "female", 0.625),
        (0.05, "female", 0.875),
        (0.0, "female", 1.0),
    ],
)
def test_decide_gender(p_male, gender, confidence):
    result = decide_gender(p_male, male_threshold=0.2, min_confidence=0.55)
    assert result.confidence == pytest.approx(confidence, abs=1e-4)
    assert result.gender == gender


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


def test_long_turns_are_classified_in_pieces(mock_model, monkeypatch):
    lengths = []

    class RecordingAudio(MockAudioSegment):
        def __getitem__(self, val):
            lengths.append(val.stop - val.start)
            return self

    monkeypatch.setattr("app.services.gender.AudioSegment.from_wav", lambda x: RecordingAudio(300000))

    result = predict_speakers_gender("dummy.wav", [_seg(0, 222.8)])

    assert result["S"].gender == "male"
    assert lengths == [10000] * 6
