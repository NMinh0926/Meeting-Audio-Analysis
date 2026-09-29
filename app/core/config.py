"""Application configuration loaded from .env file."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings read from environment variables / .env file."""

    # Directories
    UPLOAD_DIR: str = "data/uploads"
    TEMP_DIR: str = "data/temp"

    # Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_LANGUAGE: str = "vi"
    DEVICE: str = "cpu"
    COMPUTE_TYPE: str = "int8"

    # Diarization
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    # Merge
    MERGE_GAP_SECONDS: float = 2.0

    # Gender
    GENDER_MODEL: str = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-oswg"
    MIN_GENDER_DURATION: float = 0.5  # seconds

    # Sentiment
    SENTIMENT_MODEL: str = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"

    # Hugging Face
    HF_TOKEN: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

