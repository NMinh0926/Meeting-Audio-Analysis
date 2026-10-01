"""Emotion per turn, from the voice and from the words (see docs/benchmarks/2026-10-01-emotion.md).

Voice: emotion2vec+ large on the turn's audio, in short pieces. Words: a PhoBERT model fine-tuned on
UIT-VSMEC, sentence by sentence. Both are folded into the app emotions (`emotion_labels`) and combined
with EMOTION_VOICE_WEIGHT on the voice.
"""
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from pydub import AudioSegment

from app.core.config import get_settings
from app.models.schemas import SentimentResult, SpeakerTurn
from app.services.emotion_labels import EMOTIONS, TEXT_LABELS, VOICE_LABELS, to_emotions

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
Scores = dict[str, float]

_text_classifier: Any = None
_voice_model: Any = None


def get_text_classifier() -> Any:
    global _text_classifier
    if _text_classifier is None:
        from transformers import pipeline

        settings = get_settings()
        _text_classifier = pipeline("text-classification", model=settings.EMOTION_TEXT_MODEL,
                                    device=settings.EMOTION_TEXT_DEVICE, top_k=None)
    return _text_classifier


def get_voice_model() -> Any:
    global _voice_model
    if _voice_model is None:
        from funasr import AutoModel

        settings = get_settings()
        _voice_model = AutoModel(model=settings.EMOTION_VOICE_MODEL, hub="hf", device=settings.DEVICE,
                                 disable_update=True, disable_pbar=True)
    return _voice_model


def weighted_mean(parts: Sequence[tuple[Scores, float]]) -> Scores | None:
    """Average of emotion scores weighted by duration; None when there is nothing to average."""
    total = sum(weight for _, weight in parts)
    if total <= 0:
        return None
    return {e: sum(scores[e] * weight for scores, weight in parts) / total for e in EMOTIONS}


def combine(voice: Scores | None, text: Scores | None, voice_weight: float, min_margin: float) -> SentimentResult:
    """Mix voice and text scores; the side that is missing leaves the other alone.

    An emotion other than neutral must beat neutral by `min_margin`, otherwise the turn is neutral: a near tie
    is usually one confident side against the other (e.g. a question the voice model hears as sad).
    """
    if voice is None and text is None:
        return SentimentResult(sentiment="neutral", confidence=0.0)
    if voice is None or text is None:
        scores = voice or text
    else:
        scores = {e: voice_weight * voice[e] + (1 - voice_weight) * text[e] for e in EMOTIONS}
    emotion = max(EMOTIONS, key=scores.__getitem__)
    if emotion != "neutral" and scores[emotion] - scores["neutral"] < min_margin:
        emotion = "neutral"
    return SentimentResult(sentiment=emotion, confidence=round(scores[emotion], 4))


def voice_scores(samples: np.ndarray, chunk_seconds: float, min_seconds: float) -> Scores | None:
    """Voice emotion of a 16 kHz mono waveform, averaged over pieces of at most `chunk_seconds`.

    The model's memory grows with the square of its input length, so long turns are cut up.
    Pieces shorter than `min_seconds` carry too little voice and are skipped.
    """
    model = get_voice_model()
    size = int(chunk_seconds * SAMPLE_RATE)
    parts = []
    for begin in range(0, len(samples), size):
        piece = samples[begin:begin + size]
        if len(piece) < min_seconds * SAMPLE_RATE:
            continue
        result = model.generate(piece, granularity="utterance", extract_embedding=False, disable_pbar=True)[0]
        parts.append((to_emotions(dict(zip(result["labels"], result["scores"])), VOICE_LABELS), len(piece)))
    return weighted_mean(parts)


def text_scores(sentences: Sequence[tuple[str, float]]) -> Scores | None:
    """Text emotion of (sentence, duration) pairs, classified one sentence at a time like the training data."""
    sentences = [(text.strip(), duration) for text, duration in sentences if text.strip()]
    if not sentences:
        return None
    results = get_text_classifier()([text for text, _ in sentences], truncation=True, max_length=256)
    parts = [
        (to_emotions({s["label"]: s["score"] for s in result}, TEXT_LABELS), max(duration, 0.1))
        for result, (_, duration) in zip(results, sentences)
    ]
    return weighted_mean(parts)


def _sentences(turn: SpeakerTurn) -> list[tuple[str, float]]:
    if turn.utterances:
        return [(u.text, u.end - u.start) for u in turn.utterances]
    return [(turn.text, turn.end - turn.start)]


def predict_turn_emotions(normalized_audio_path: str | Path, turns: Sequence[SpeakerTurn]) -> list[SentimentResult]:
    """Emotion of each turn. A side that fails (model or audio) is left out rather than failing the job."""
    settings = get_settings()
    try:
        audio = AudioSegment.from_wav(str(normalized_audio_path))
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
    except Exception as e:
        logger.error(f"Cannot read audio for voice emotion, using text only: {e}")
        samples = None

    results = []
    for turn in turns:
        voice = text = None
        if samples is not None:
            try:
                segment = samples[int(turn.start * SAMPLE_RATE):int(turn.end * SAMPLE_RATE)]
                voice = voice_scores(segment, settings.EMOTION_CHUNK_SECONDS, settings.EMOTION_MIN_SECONDS)
                if voice is None:
                    # Too short to hear ("Năm.", "Cái"): a word alone is not enough for the text model,
                    # which called 6 of 15 such turns angry, so the silent voice side votes neutral.
                    voice = {e: float(e == "neutral") for e in EMOTIONS}
            except Exception as e:
                logger.warning(f"Voice emotion failed at {turn.start:.1f}-{turn.end:.1f}s: {e}")
        try:
            text = text_scores(_sentences(turn))
        except Exception as e:
            logger.warning(f"Text emotion failed at {turn.start:.1f}-{turn.end:.1f}s: {e}")
        results.append(combine(voice, text, settings.EMOTION_VOICE_WEIGHT, settings.EMOTION_MIN_MARGIN))
    return results
