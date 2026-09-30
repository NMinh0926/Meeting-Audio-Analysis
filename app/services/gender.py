"""Gender classification service."""
from pathlib import Path
from typing import Any
import logging

import numpy as np
from pydub import AudioSegment

from app.core.config import get_settings
from app.models.schemas import SpeakerSegment, GenderResult

logger = logging.getLogger(__name__)

# Global model instance
_gender_pipeline: Any = None

def get_gender_pipeline() -> Any:
    global _gender_pipeline
    if _gender_pipeline is None:
        settings = get_settings()
        try:
            from transformers import pipeline
            _gender_pipeline = pipeline(
                "audio-classification", 
                model=settings.GENDER_MODEL,
                device=settings.DEVICE
            )
        except Exception as e:
            logger.error(f"Failed to load gender model: {e}")
            raise
    return _gender_pipeline

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
    """Predicts gender for each speaker by aggregating audio segments.
    
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
        classifier = get_gender_pipeline()
        audio = AudioSegment.from_wav(str(normalized_audio_path))
    except Exception as e:
        logger.error(f"Error loading audio or model for gender classification: {e}")
        # Fallback for all if model fails to load
        for spk in segments_by_speaker:
            result[spk] = GenderResult(gender="unknown", confidence=0.0)
        return result

    for speaker, segments in segments_by_speaker.items():
        total_duration = 0.0
        weighted_scores = {"male": 0.0, "female": 0.0}
        
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
                preds = classifier(samples)
                # preds is like [{'score': 0.9, 'label': 'male'}, ...]
                scores_dict = {p['label'].lower(): p['score'] for p in preds}
                
                # We expect 'male' and 'female' labels
                male_score = scores_dict.get('male', 0.0)
                female_score = scores_dict.get('female', 0.0)
                
                weighted_scores["male"] += male_score * duration
                weighted_scores["female"] += female_score * duration
                total_duration += duration
                
            except Exception as e:
                logger.warning(f"Failed to classify gender for {speaker} at {start:.1f}-{end:.1f}s: {e}")
                
        if total_duration > 0:
            avg_male = weighted_scores["male"] / total_duration
            avg_female = weighted_scores["female"] / total_duration
            
            if avg_male > avg_female:
                final_gender = "male"
                final_conf = avg_male
            else:
                final_gender = "female"
                final_conf = avg_female
                
            if final_conf < settings.GENDER_MIN_CONFIDENCE:
                # The model hesitates between the two: say so instead of guessing.
                final_gender = "unknown"

            result[speaker] = GenderResult(
                gender=final_gender,
                confidence=round(final_conf, 4)
            )
        else:
            # Not enough data
            result[speaker] = GenderResult(gender="unknown", confidence=0.0)
            
    return result

