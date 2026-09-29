"""Speaker diarization using pyannote.audio."""
from pathlib import Path
from typing import Any
from app.core.config import get_settings
from app.models.schemas import SpeakerSegment

class DiarizationError(Exception):
    pass

class DiarizationAuthError(DiarizationError):
    pass

class NoSpeakerDetectedError(DiarizationError):
    pass

# Global pipeline instance for reuse
_pipeline: Any = None

def get_diarization_pipeline() -> Any:
    global _pipeline
    if _pipeline is None:
        settings = get_settings()
        if not settings.HF_TOKEN:
            raise DiarizationAuthError("Hugging Face token is missing in configuration. HF_TOKEN is required.")
            
        try:
            from pyannote.audio import Pipeline
            # Load pipeline with auth token
            _pipeline = Pipeline.from_pretrained(
                settings.DIARIZATION_MODEL,
                use_auth_token=settings.HF_TOKEN
            )
            if _pipeline is None:
                raise DiarizationError("Failed to initialize pipeline. Check model name or token permissions.")
                
            # Send to device
            import torch
            device = torch.device(settings.DEVICE)
            _pipeline.to(device)
            
        except Exception as e:
            if isinstance(e, DiarizationAuthError):
                raise
            raise DiarizationError(f"Failed to load diarization pipeline: {e}") from e
            
    return _pipeline

def diarize_audio(audio_path: str | Path) -> list[SpeakerSegment]:
    """Diarizes audio to identify speaker segments.

    Returns:
        List of SpeakerSegment containing speaker, start, end.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
    pipeline = get_diarization_pipeline()
    try:
        # Run inference
        diarization = pipeline(str(audio_path))
        
        result = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            result.append(SpeakerSegment(
                speaker=speaker,
                start=turn.start,
                end=turn.end
            ))
            
        if not result:
            raise NoSpeakerDetectedError("No speaker detected in audio")
            
        return result
    except Exception as e:
        if isinstance(e, NoSpeakerDetectedError):
            raise
        raise DiarizationError(f"Diarization failed: {e}") from e

