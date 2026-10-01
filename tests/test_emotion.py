"""Tests for emotion per turn (voice + text). Both models are replaced by fakes."""
import sys
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from app.core.config import get_settings
from app.models.schemas import SpeakerTurn, TranscriptSegment
from app.services import emotion
from app.services.emotion_labels import EMOTIONS, TEXT_LABELS, VOICE_LABELS, to_emotions


def one_hot(name: str, value: float = 1.0) -> dict[str, float]:
    return {e: (value if e == name else (1 - value) / (len(EMOTIONS) - 1)) for e in EMOTIONS}


# --- label folding

def test_to_emotions_folds_vsmec_labels_and_merges_disgust_into_anger():
    folded = to_emotions({"Anger": 0.3, "Disgust": 0.3, "Enjoyment": 0.4}, TEXT_LABELS)
    assert folded["angry"] == pytest.approx(0.6)
    assert folded["happy"] == pytest.approx(0.4)
    assert sum(folded.values()) == pytest.approx(1.0)


def test_to_emotions_reads_the_english_half_of_emotion2vec_labels_and_renormalises():
    folded = to_emotions({"开心/happy": 0.5, "中立/neutral": 0.3, "<unk>": 0.2}, VOICE_LABELS)
    assert folded["happy"] == pytest.approx(0.5 / 0.8)
    assert folded["neutral"] == pytest.approx(0.3 / 0.8)


def test_to_emotions_without_known_labels_is_neutral():
    assert to_emotions({"whatever": 1.0}, TEXT_LABELS) == one_hot("neutral")


# --- combining

def test_weighted_mean_weights_by_duration():
    mean = emotion.weighted_mean([(one_hot("happy"), 3.0), (one_hot("sad"), 1.0)])
    assert mean["happy"] == pytest.approx(0.75)
    assert mean["sad"] == pytest.approx(0.25)


def test_weighted_mean_of_nothing_is_none():
    assert emotion.weighted_mean([]) is None


def test_combine_leans_on_the_voice():
    result = emotion.combine(one_hot("neutral"), one_hot("angry"), voice_weight=0.6)
    assert (result.sentiment, result.confidence) == ("neutral", 0.6)


def test_combine_agreeing_sides():
    result = emotion.combine(one_hot("happy", 0.8), one_hot("happy", 0.6), voice_weight=0.6)
    assert (result.sentiment, result.confidence) == ("happy", pytest.approx(0.72))


@pytest.mark.parametrize(("voice", "text", "expected"), [
    (one_hot("sad", 0.7), None, ("sad", 0.7)),
    (None, one_hot("surprised", 0.9), ("surprised", 0.9)),
    (None, None, ("neutral", 0.0)),
])
def test_combine_with_a_missing_side(voice, text, expected):
    result = emotion.combine(voice, text, voice_weight=0.6)
    assert (result.sentiment, result.confidence) == expected


# --- voice

class FakeVoiceModel:
    """emotion2vec+ stand-in: "happy" for loud pieces, "neutral" for quiet ones; records piece lengths."""

    def __init__(self):
        self.pieces: list[int] = []

    def generate(self, piece, **kwargs):
        self.pieces.append(len(piece))
        loud = float(np.abs(piece).mean()) > 0.25
        return [{"labels": ["开心/happy", "中立/neutral"], "scores": [1.0, 0.0] if loud else [0.0, 1.0]}]


@pytest.fixture
def voice_model(monkeypatch):
    model = FakeVoiceModel()
    monkeypatch.setattr(emotion, "get_voice_model", lambda: model)
    return model


def test_voice_scores_cuts_long_audio_and_weights_pieces_by_length(voice_model):
    sr = emotion.SAMPLE_RATE
    samples = np.concatenate([np.full(20 * sr, 0.5), np.full(5 * sr, 0.0)]).astype(np.float32)

    scores = emotion.voice_scores(samples, chunk_seconds=10, min_seconds=0.5)

    assert voice_model.pieces == [10 * sr, 10 * sr, 5 * sr]
    assert scores["happy"] == pytest.approx(0.8)
    assert scores["neutral"] == pytest.approx(0.2)


def test_voice_scores_skips_short_pieces(voice_model):
    sr = emotion.SAMPLE_RATE
    samples = np.full(int(10.3 * sr), 0.5, dtype=np.float32)

    emotion.voice_scores(samples, chunk_seconds=10, min_seconds=0.5)

    assert voice_model.pieces == [10 * sr]
    assert emotion.voice_scores(samples[: sr // 4], chunk_seconds=10, min_seconds=0.5) is None


# --- text

class FakeTextClassifier:
    """VSMEC model stand-in: "Enjoyment" when the sentence says "vui", "Other" otherwise."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, texts, **kwargs):
        self.calls.append(list(texts))
        return [[{"label": "Enjoyment", "score": 0.9}, {"label": "Other", "score": 0.1}] if "vui" in t
                else [{"label": "Other", "score": 1.0}] for t in texts]


@pytest.fixture
def text_classifier(monkeypatch):
    classifier = FakeTextClassifier()
    monkeypatch.setattr(emotion, "get_text_classifier", lambda: classifier)
    return classifier


def test_text_scores_classifies_each_sentence_and_weights_by_duration(text_classifier):
    scores = emotion.text_scores([("Rất vui.", 1.0), ("  ", 5.0), ("Bắt đầu họp.", 3.0)])

    assert text_classifier.calls == [["Rất vui.", "Bắt đầu họp."]]
    assert scores["happy"] == pytest.approx(0.9 * 0.25)
    assert scores["neutral"] == pytest.approx(0.1 * 0.25 + 0.75)


def test_text_scores_without_words_is_none(text_classifier):
    assert emotion.text_scores([("", 1.0), ("   ", 2.0)]) is None
    assert text_classifier.calls == []


# --- per turn

def _wav(path, seconds_and_levels: list[tuple[float, float]]) -> None:
    samples = np.concatenate([np.full(int(s * emotion.SAMPLE_RATE), level) for s, level in seconds_and_levels])
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(emotion.SAMPLE_RATE)
        wf.writeframes((samples * 32767).astype(np.int16).tobytes())


def _turn(start: float, end: float, *sentences: str) -> SpeakerTurn:
    step = (end - start) / len(sentences)
    utterances = [TranscriptSegment(start=start + i * step, end=start + (i + 1) * step, text=s)
                  for i, s in enumerate(sentences)]
    return SpeakerTurn(speaker="SPEAKER_00", start=start, end=end, text=" ".join(sentences), utterances=utterances)


def test_predict_turn_emotions_combines_voice_and_text_per_turn(voice_model, text_classifier, tmp_path):
    audio = tmp_path / "normalized.wav"
    _wav(audio, [(4.0, 0.5), (4.0, 0.0)])  # loud first turn, quiet second
    turns = [_turn(0.0, 4.0, "Hôm nay vui quá."), _turn(4.0, 8.0, "Bắt đầu họp.")]

    results = emotion.predict_turn_emotions(audio, turns)

    assert [(r.sentiment, r.confidence) for r in results] == [("happy", pytest.approx(0.96)), ("neutral", 1.0)]


def test_predict_turn_emotions_falls_back_to_text_when_the_audio_cannot_be_read(voice_model, text_classifier, tmp_path):
    results = emotion.predict_turn_emotions(tmp_path / "missing.wav", [_turn(0.0, 2.0, "Vui ghê, vui thật.")])

    assert voice_model.pieces == []
    assert [(r.sentiment, r.confidence) for r in results] == [("happy", 0.9)]


def test_predict_turn_emotions_survives_a_failing_voice_model(monkeypatch, text_classifier, tmp_path):
    audio = tmp_path / "normalized.wav"
    _wav(audio, [(2.0, 0.5)])

    def broken():
        raise RuntimeError("CUDA out of memory")
    monkeypatch.setattr(emotion, "get_voice_model", broken)

    results = emotion.predict_turn_emotions(audio, [_turn(0.0, 2.0, "Bắt đầu họp.")])

    assert [(r.sentiment, r.confidence) for r in results] == [("neutral", 1.0)]


# --- model loading (fake modules: nothing is downloaded)

def test_text_model_loads_on_its_own_device(monkeypatch):
    calls = {}
    monkeypatch.setattr(emotion, "_text_classifier", None)
    monkeypatch.setattr(get_settings(), "EMOTION_TEXT_DEVICE", "cpu")
    fake = SimpleNamespace(pipeline=lambda task, **kwargs: calls.update(kwargs, task=task) or object())
    monkeypatch.setitem(sys.modules, "transformers", fake)

    emotion.get_text_classifier()

    assert calls["task"] == "text-classification"
    assert calls["device"] == "cpu"
    assert calls["model"] == get_settings().EMOTION_TEXT_MODEL
    assert calls["top_k"] is None


def test_voice_model_loads_from_hugging_face_on_the_audio_device(monkeypatch):
    calls = {}
    monkeypatch.setattr(emotion, "_voice_model", None)
    monkeypatch.setattr(get_settings(), "DEVICE", "cuda")
    fake = SimpleNamespace(AutoModel=lambda **kwargs: calls.update(kwargs) or object())
    monkeypatch.setitem(sys.modules, "funasr", fake)

    emotion.get_voice_model()

    assert (calls["model"], calls["hub"], calls["device"]) == (get_settings().EMOTION_VOICE_MODEL, "hf", "cuda")
    assert calls["disable_update"] is True
