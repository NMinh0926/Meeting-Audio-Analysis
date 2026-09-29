"""Tests for app.services.audio_preprocessing."""

import math
import struct
import tempfile
import wave
from pathlib import Path

import pytest

from app.services.audio_preprocessing import (
    CorruptAudioError,
    EmptyAudioError,
    UnsupportedFormatError,
    preprocess_audio,
)

# ---------------------------------------------------------------------------
# Helpers — generate synthetic WAV files using only the stdlib
# ---------------------------------------------------------------------------

SAMPLE_RATE_44100 = 44_100
DURATION_SEC = 2


def _generate_wav(
    path: Path,
    *,
    sample_rate: int = SAMPLE_RATE_44100,
    channels: int = 2,
    duration: float = DURATION_SEC,
    freq: float = 440.0,
) -> Path:
    """Write a valid WAV file containing a sine tone.

    Parameters
    ----------
    path: destination file path.
    sample_rate: samples per second.
    channels: 1 (mono) or 2 (stereo).
    duration: length in seconds.
    freq: sine wave frequency in Hz.
    """
    n_frames = int(sample_rate * duration)
    max_amp = 32_767  # 16-bit signed

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        for i in range(n_frames):
            sample = int(max_amp * math.sin(2.0 * math.pi * freq * i / sample_rate))
            # Write same sample to all channels
            frame = struct.pack("<h", sample) * channels
            wf.writeframesraw(frame)

    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Return pytest's tmp_path for convenience."""
    return tmp_path


@pytest.fixture()
def stereo_wav_44100(tmp_dir: Path) -> Path:
    """Create a stereo 44.1 kHz WAV file."""
    return _generate_wav(tmp_dir / "stereo_44100.wav", sample_rate=44_100, channels=2)


@pytest.fixture()
def mono_wav_16000(tmp_dir: Path) -> Path:
    """Create a mono 16 kHz WAV file (already normalised)."""
    return _generate_wav(
        tmp_dir / "mono_16000.wav", sample_rate=16_000, channels=1
    )


@pytest.fixture()
def stereo_wav_48000(tmp_dir: Path) -> Path:
    """Create a stereo 48 kHz WAV file."""
    return _generate_wav(tmp_dir / "stereo_48000.wav", sample_rate=48_000, channels=2)


@pytest.fixture()
def empty_wav(tmp_dir: Path) -> Path:
    """Create a 0-byte file with .wav extension."""
    p = tmp_dir / "empty.wav"
    p.write_bytes(b"")
    return p


@pytest.fixture()
def corrupt_wav(tmp_dir: Path) -> Path:
    """Create a file with .wav extension containing garbage bytes."""
    p = tmp_dir / "corrupt.wav"
    p.write_bytes(b"\x00\xff\xfe\xfd" * 100)
    return p


# ---------------------------------------------------------------------------
# Tests — valid WAV inputs
# ---------------------------------------------------------------------------


class TestValidWAV:
    """Tests with valid WAV files that require normalisation."""

    def test_stereo_44100_normalises_to_mono_16000(
        self, stereo_wav_44100: Path, monkeypatch, tmp_dir: Path
    ):
        """A stereo 44.1 kHz WAV should become mono 16 kHz."""
        monkeypatch.setenv("TEMP_DIR", str(tmp_dir / "output"))

        result = preprocess_audio(stereo_wav_44100)

        # Original metadata
        assert result.original.channels == 2
        assert result.original.sample_rate == 44_100

        # Normalised metadata
        assert result.normalized.channels == 1
        assert result.normalized.sample_rate == 16_000
        assert result.normalized.filename.endswith("_normalized.wav")

        # Output file exists and is non-empty
        out = Path(result.normalized_path)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_stereo_48000_normalises_to_mono_16000(
        self, stereo_wav_48000: Path, monkeypatch, tmp_dir: Path
    ):
        """A stereo 48 kHz WAV should become mono 16 kHz."""
        monkeypatch.setenv("TEMP_DIR", str(tmp_dir / "output"))

        result = preprocess_audio(stereo_wav_48000)

        assert result.normalized.channels == 1
        assert result.normalized.sample_rate == 16_000

    def test_already_normalised_stays_correct(
        self, mono_wav_16000: Path, monkeypatch, tmp_dir: Path
    ):
        """A mono 16 kHz WAV should still produce correct output."""
        monkeypatch.setenv("TEMP_DIR", str(tmp_dir / "output"))

        result = preprocess_audio(mono_wav_16000)

        assert result.original.channels == 1
        assert result.original.sample_rate == 16_000
        assert result.normalized.channels == 1
        assert result.normalized.sample_rate == 16_000

    def test_output_is_valid_wav_pcm(
        self, stereo_wav_44100: Path, monkeypatch, tmp_dir: Path
    ):
        """The output file should be readable as a valid WAV."""
        monkeypatch.setenv("TEMP_DIR", str(tmp_dir / "output"))

        result = preprocess_audio(stereo_wav_44100)

        with wave.open(result.normalized_path, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16_000
            assert wf.getsampwidth() == 2  # 16-bit PCM

    def test_duration_preserved_approximately(
        self, stereo_wav_44100: Path, monkeypatch, tmp_dir: Path
    ):
        """Duration should remain approximately the same after normalisation."""
        monkeypatch.setenv("TEMP_DIR", str(tmp_dir / "output"))

        result = preprocess_audio(stereo_wav_44100)

        assert abs(result.original.duration_seconds - result.normalized.duration_seconds) < 0.1


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for invalid/edge-case inputs."""

    def test_unsupported_format_raises(self, tmp_dir: Path):
        """A .ogg file should raise UnsupportedFormatError."""
        p = tmp_dir / "audio.ogg"
        p.write_bytes(b"fake ogg content")

        with pytest.raises(UnsupportedFormatError):
            preprocess_audio(p)

    def test_file_not_found_raises(self, tmp_dir: Path):
        """A non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            preprocess_audio(tmp_dir / "does_not_exist.wav")

    def test_empty_file_raises(self, empty_wav: Path):
        """A 0-byte .wav should raise EmptyAudioError."""
        with pytest.raises(EmptyAudioError):
            preprocess_audio(empty_wav)

    def test_corrupt_file_raises(self, corrupt_wav: Path):
        """Random garbage bytes with .wav extension should raise CorruptAudioError."""
        with pytest.raises(CorruptAudioError):
            preprocess_audio(corrupt_wav)

    def test_txt_renamed_to_wav_raises(self, tmp_dir: Path):
        """A text file renamed to .wav should raise CorruptAudioError."""
        p = tmp_dir / "fake.wav"
        p.write_text("this is not audio at all", encoding="utf-8")

        with pytest.raises(CorruptAudioError):
            preprocess_audio(p)
