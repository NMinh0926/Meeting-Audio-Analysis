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
    # large-v3-turbo: 5.9 % WER on Vietnamese vs 25.9 % for base (docs/benchmarks/2026-09-30-asr-models.md)
    WHISPER_MODEL: str = "large-v3-turbo"
    WHISPER_LANGUAGE: str = "vi"
    # Skip silence before decoding: fewer hallucinated sentences on pauses
    WHISPER_VAD: bool = True
    COMPUTE_TYPE: str = "int8"

    # Diarization
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    # Merge
    MERGE_GAP_SECONDS: float = 2.0

    # Gender
    # ECAPA-TDNN (MIT): 120/120 on held-out Vietnamese FLEURS voices with the 0.2 male threshold
    GENDER_MODEL: str = "JaesungHuh/voice-gender-classifier"
    MIN_GENDER_DURATION: float = 0.5  # seconds
    # Audio classified per speaker: pieces of at most GENDER_CHUNK_SECONDS, GENDER_SECONDS_PER_SPEAKER in total
    GENDER_CHUNK_SECONDS: float = 10.0
    GENDER_SECONDS_PER_SPEAKER: float = 60.0
    # Average male probability from which a speaker is male (the model under-rates Vietnamese men)
    GENDER_MALE_THRESHOLD: float = 0.2
    # Below this confidence (distance from the threshold, 0.5..1) the speaker is reported as "unknown"
    GENDER_MIN_CONFIDENCE: float = 0.55

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

