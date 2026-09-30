"""Application configuration loaded from .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings read from environment variables / .env file."""

    # Working directory for intermediate audio
    TEMP_DIR: str = "data/temp"

    # PostgreSQL (compose builds DATABASE_URL from POSTGRES_*)
    DATABASE_URL: str = "postgresql+psycopg://meeting:meeting_dev_password@localhost:5432/meeting"

    # S3-compatible object storage for original recordings
    S3_ENDPOINT: str = "http://localhost:8333"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "meetings"
    S3_REGION: str = "us-east-1"

    # Upload limits
    MAX_UPLOAD_MB: int = 500

    # Worker: seconds to wait before polling again when the queue is empty
    WORKER_POLL_SECONDS: float = 2.0

    # Inference device for every model: "cpu" or "cuda"
    DEVICE: str = "cpu"

    # Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_LANGUAGE: str = "vi"
    COMPUTE_TYPE: str = "int8"

    # Diarization
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    # Merge
    MERGE_GAP_SECONDS: float = 2.0

    # Gender
    GENDER_MODEL: str = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
    MIN_GENDER_DURATION: float = 0.5  # seconds

    # Sentiment
    SENTIMENT_MODEL: str = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"

    # Hugging Face
    HF_TOKEN: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # .env also holds compose-only keys (POSTGRES_*, S3_*)
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

