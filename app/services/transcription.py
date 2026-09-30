"""STT using faster-whisper."""
from pathlib import Path
from typing import Any
from app.core.config import get_settings
from app.models.schemas import TranscriptSegment, Word

class TranscriptionError(Exception):
    pass

class NoSpeechDetectedError(TranscriptionError):
    pass

# Global model instance for reuse
_model: Any = None

def get_whisper_model() -> Any:
    global _model
    if _model is None:
        settings = get_settings()
        try:
            from faster_whisper import WhisperModel
            _model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.DEVICE,
                compute_type=settings.COMPUTE_TYPE
            )
        except Exception as e:
            raise TranscriptionError(f"Failed to load Whisper model: {e}") from e
    return _model

def transcribe_audio(audio_path: str | Path) -> list[TranscriptSegment]:
    """Transcribes audio using faster-whisper.

    Returns:
        List of TranscriptSegment objects containing start, end, and text.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    settings = get_settings()
    model = get_whisper_model()
    
    try:
        # Transcribe
        segments, info = model.transcribe(
            str(audio_path),
            language=settings.WHISPER_LANGUAGE,
            vad_filter=settings.WHISPER_VAD,
            word_timestamps=True,
        )
        
        result = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                words = [
                    Word(start=w.start, end=w.end, text=w.word)
                    for w in (segment.words or [])
                ]
                result.append(TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=text,
                    words=words
                ))
                
        if not result:
            raise NoSpeechDetectedError("No speech detected in audio")
            
        return result
    except Exception as e:
        if isinstance(e, NoSpeechDetectedError):
            raise
        raise TranscriptionError(f"Transcription failed: {e}") from e

