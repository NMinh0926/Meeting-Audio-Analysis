"""Gender classification service (ECAPA-TDNN, see docs/benchmarks/2026-10-01-speakers-gender.md)."""
from pathlib import Path
from typing import Any
import logging

import numpy as np
from pydub import AudioSegment

from app.core.config import get_settings
from app.models.schemas import SpeakerSegment, GenderResult

logger = logging.getLogger(__name__)

# Global model instance
_gender_model: Any = None

def get_gender_model() -> Any:
    global _gender_model
    if _gender_model is None:
        settings = get_settings()
        try:
            from app.services.ecapa_gender import ECAPAGender
            _gender_model = ECAPAGender.from_pretrained(settings.GENDER_MODEL).to(settings.DEVICE).eval()
        except Exception as e:
            logger.error(f"Failed to load gender model: {e}")
            raise
    return _gender_model

def male_probability(samples: np.ndarray) -> float:
    """Probability that a 16 kHz mono float waveform is a male voice."""
    import torch

    from app.services.ecapa_gender import MALE

    model = get_gender_model()
    with torch.inference_mode():
        waveform = torch.from_numpy(samples).unsqueeze(0).to(get_settings().DEVICE)
        return float(torch.softmax(model(waveform), dim=1)[0, MALE])

def decide_gender(p_male: float, male_threshold: float, min_confidence: float) -> GenderResult:
    """Turn an average male probability into a label and a confidence in [0.5, 1].

    The model under-rates Vietnamese male voices, so "male" starts at `male_threshold` rather than 0.5.
    Confidence is the distance from that threshold, rescaled to each side; below `min_confidence`
    the speaker is too close to call and is reported as "unknown".
    """
    if p_male >= male_threshold:
        gender, confidence = "male", 0.5 + 0.5 * (p_male - male_threshold) / (1 - male_threshold)
    else:
        gender, confidence = "female", 0.5 + 0.5 * (male_threshold - p_male) / male_threshold
    if confidence < min_confidence:
        gender = "unknown"
    return GenderResult(gender=gender, confidence=round(confidence, 4))

def select_chunks(
    segments: list[SpeakerSegment],
    min_duration: float,
    chunk_seconds: float,
    budget_seconds: float,
) -> list[tuple[float, float]]:
    """Pick the parts of one speaker's audio to classify.

    Longest segments first (cleanest speech), cut into pieces of at most `chunk_seconds`, until
    `budget_seconds` are collected. Pieces shorter than `min_duration` are skipped. Bounding both
    keeps long meetings fast and each model input small.
    """
    chunks: list[tuple[float, float]] = []
    total = 0.0
    for seg in sorted(segments, key=lambda s: s.end - s.start, reverse=True):
        start = seg.start
        while total < budget_seconds:
            end = min(seg.end, start + chunk_seconds, start + budget_seconds - total)
            if end - start < min_duration:
                break
            chunks.append((start, end))
            total += end - start
            start = end
        if total >= budget_seconds:
            break
    return chunks


def predict_speakers_gender(
    normalized_audio_path: str | Path,
    speaker_segments: list[SpeakerSegment]
) -> dict[str, GenderResult]:
    """Predicts gender for each speaker by averaging the model over pieces of their speech.

    Returns:
        Dictionary mapping speaker label to GenderResult.
    """
    settings = get_settings()

    # Group segments by speaker
    segments_by_speaker: dict[str, list[SpeakerSegment]] = {}
    for seg in speaker_segments:
        segments_by_speaker.setdefault(seg.speaker, []).append(seg)

    result = {}

    if not segments_by_speaker:
        return result

    try:
        get_gender_model()
        audio = AudioSegment.from_wav(str(normalized_audio_path))
    except Exception as e:
        logger.error(f"Error loading audio or model for gender classification: {e}")
        # Fallback for all if model fails to load
        for spk in segments_by_speaker:
            result[spk] = GenderResult(gender="unknown", confidence=0.0)
        return result

    for speaker, segments in segments_by_speaker.items():
        total_duration = 0.0
        weighted_male = 0.0

        chunks = select_chunks(
            segments,
            min_duration=settings.MIN_GENDER_DURATION,
            chunk_seconds=settings.GENDER_CHUNK_SECONDS,
            budget_seconds=settings.GENDER_SECONDS_PER_SPEAKER,
        )
        for start, end in chunks:
            duration = end - start
            chunk = audio[int(start * 1000):int(end * 1000)]

            # Convert to float32 numpy array
            samples = np.array(chunk.get_array_of_samples(), dtype=np.float32) / 32768.0

            try:
                weighted_male += male_probability(samples) * duration
                total_duration += duration
            except Exception as e:
                logger.warning(f"Failed to classify gender for {speaker} at {start:.1f}-{end:.1f}s: {e}")

        if total_duration > 0:
            result[speaker] = decide_gender(
                weighted_male / total_duration,
                male_threshold=settings.GENDER_MALE_THRESHOLD,
                min_confidence=settings.GENDER_MIN_CONFIDENCE,
            )
        else:
            # Not enough data
            result[speaker] = GenderResult(gender="unknown", confidence=0.0)

    return result
