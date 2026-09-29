"""Speaker diarization using pyannote.audio."""
import wave
from pathlib import Path
from typing import Any

import numpy as np

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
                token=settings.HF_TOKEN
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

def _load_waveform(audio_path: Path) -> dict[str, Any]:
    """Read a 16-bit PCM WAV into the in-memory input pyannote accepts.

    Bypasses pyannote's own decoder (torchcodec), which needs FFmpeg libraries matching its build.
    """
    import torch

    with wave.open(str(audio_path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise DiarizationError(f"Expected 16-bit PCM WAV: {audio_path}")
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    waveform = torch.from_numpy(samples.reshape(-1, channels).T.copy())
    return {"waveform": waveform, "sample_rate": sample_rate}

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
        output = pipeline(_load_waveform(audio_path))
        # pyannote 4 wraps annotations in DiarizeOutput; the exclusive variant has no
        # overlapping turns, which suits aligning each transcript segment to one speaker.
        diarization = getattr(
            output, "exclusive_speaker_diarization",
            getattr(output, "speaker_diarization", output)
        )

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

