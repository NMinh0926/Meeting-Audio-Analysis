"""Audio preprocessing service.

Normalises an input audio file (WAV / MP3 / M4A) to:
  - WAV PCM format
  - mono channel
  - 16 kHz sample rate

Saves the normalised file into the configured TEMP_DIR and returns
metadata for both the original and normalised audio.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# FFmpeg auto-discovery: use imageio-ffmpeg bundled binary if system ffmpeg
# is not found.  Must run BEFORE importing pydub so it picks up the path.
# ---------------------------------------------------------------------------


def _ensure_ffmpeg_on_path() -> None:
    """Add the imageio-ffmpeg binary directory to PATH if ffmpeg is missing."""
    if shutil.which("ffmpeg") is not None:
        return  # system ffmpeg already available
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = str(Path(ffmpeg_exe).parent)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass  # caller will get a pydub error later if ffmpeg is truly missing


_ensure_ffmpeg_on_path()

from pydub import AudioSegment  # noqa: E402
from pydub.exceptions import CouldntDecodeError  # noqa: E402

# Explicitly point pydub at the imageio-ffmpeg binary (Windows PATH can be
# unreliable when the exe name contains version strings).
try:
    import imageio_ffmpeg as _ioff  # noqa: E402

    AudioSegment.converter = _ioff.get_ffmpeg_exe()
except Exception:
    pass

from app.core.config import get_settings
from app.models.schemas import AudioMetadata, PreprocessingResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: set[str] = {".wav", ".mp3", ".m4a"}
TARGET_SAMPLE_RATE: int = 16_000
TARGET_CHANNELS: int = 1

# Map file extension → pydub format string
_EXT_TO_FORMAT: dict[str, str] = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".m4a": "m4a",
}

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class AudioPreprocessingError(Exception):
    """Base exception for audio preprocessing failures."""


class UnsupportedFormatError(AudioPreprocessingError):
    """Raised when the audio file extension is not supported."""


class EmptyAudioError(AudioPreprocessingError):
    """Raised when the audio file is empty (0 bytes or 0 duration)."""


class CorruptAudioError(AudioPreprocessingError):
    """Raised when the audio file cannot be decoded."""


class ConversionError(AudioPreprocessingError):
    """Raised when the audio conversion/export fails."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_file(file_path: Path) -> str:
    """Validate that the file exists, is non-empty, and has a supported extension.

    Returns the lowercase extension (e.g. ".wav").

    Raises:
        FileNotFoundError: if the path does not exist.
        UnsupportedFormatError: if the extension is not supported.
        EmptyAudioError: if the file is 0 bytes.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported audio format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if file_path.stat().st_size == 0:
        raise EmptyAudioError(f"Audio file is empty (0 bytes): {file_path}")

    return ext


def _load_audio(file_path: Path, ext: str) -> AudioSegment:
    """Load an audio file into a pydub AudioSegment.

    Raises:
        CorruptAudioError: on decode failure.
        EmptyAudioError: if decoded duration is 0.
    """
    fmt = _EXT_TO_FORMAT[ext]
    try:
        audio = AudioSegment.from_file(str(file_path), format=fmt)
    except CouldntDecodeError as exc:
        raise CorruptAudioError(f"Failed to decode audio: {file_path}") from exc
    except Exception as exc:
        raise CorruptAudioError(
            f"Unexpected error decoding audio: {file_path} — {exc}"
        ) from exc

    if len(audio) == 0:
        raise EmptyAudioError(f"Decoded audio has 0 duration: {file_path}")

    return audio


def _extract_metadata(audio: AudioSegment, filename: str) -> AudioMetadata:
    """Build an AudioMetadata instance from a pydub AudioSegment."""
    return AudioMetadata(
        filename=filename,
        duration_seconds=round(len(audio) / 1000.0, 3),
        sample_rate=audio.frame_rate,
        channels=audio.channels,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def preprocess_audio(input_path: str | Path) -> PreprocessingResult:
    """Preprocess an audio file: validate, decode, normalise, and save.

    Parameters
    ----------
    input_path:
        Path to the source audio file (WAV, MP3, or M4A).

    Returns
    -------
    PreprocessingResult
        Contains original metadata, normalised metadata, and the path to
        the normalised WAV file.

    Raises
    ------
    FileNotFoundError
        Source file does not exist.
    UnsupportedFormatError
        File extension is not in SUPPORTED_EXTENSIONS.
    EmptyAudioError
        File is 0 bytes or decoded duration is 0.
    CorruptAudioError
        File cannot be decoded by ffmpeg / pydub.
    ConversionError
        Normalisation or export failed.
    """
    input_path = Path(input_path)
    settings = get_settings()

    # 1. Validate
    ext = _validate_file(input_path)

    # 2. Decode
    audio = _load_audio(input_path, ext)
    original_meta = _extract_metadata(audio, input_path.name)

    # 3. Convert to mono
    try:
        if audio.channels != TARGET_CHANNELS:
            audio = audio.set_channels(TARGET_CHANNELS)

        # 4. Resample to 16 kHz
        if audio.frame_rate != TARGET_SAMPLE_RATE:
            audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
    except Exception as exc:
        raise ConversionError(
            f"Failed to normalise audio: {exc}"
        ) from exc

    # 5. Save normalised file
    output_dir = Path(settings.TEMP_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    unique_id = uuid.uuid4().hex[:8]
    output_filename = f"{stem}_{unique_id}_normalized.wav"
    output_path = output_dir / output_filename

    try:
        audio.export(
            str(output_path),
            format="wav",
            parameters=["-acodec", "pcm_s16le"],
        )
    except Exception as exc:
        raise ConversionError(
            f"Failed to export normalised audio: {exc}"
        ) from exc

    # 6. Build result metadata
    normalized_meta = _extract_metadata(audio, output_filename)

    return PreprocessingResult(
        original=original_meta,
        normalized=normalized_meta,
        normalized_path=str(output_path),
    )
