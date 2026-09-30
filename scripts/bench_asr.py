"""Compare Whisper models on Vietnamese: word error rate, speed and GPU memory on FLEURS clips.

    docker compose run --rm -v "${PWD}:/app" api python -m scripts.bench_asr base small large-v3-turbo

Each argument is a faster-whisper model name or a path to a CTranslate2 model directory (see
`--convert`). Clips and reference texts come from `scripts.eval_gender fetch`. Stop the worker first
so the GPU is not shared.
"""
import argparse
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from scripts.eval_gender import load_manifest

CONVERTED_DIR = Path("/app/.cache/ct2")


def normalize(text: str) -> list[str]:
    """Lowercase words without punctuation, so WER counts only wording differences."""
    text = unicodedata.normalize("NFC", text.lower())
    return re.sub(r"[^\w\s]", " ", text).split()


def word_errors(reference: list[str], hypothesis: list[str]) -> int:
    """Word-level Levenshtein distance (substitutions + deletions + insertions)."""
    previous = list(range(len(hypothesis) + 1))
    for i, ref_word in enumerate(reference, start=1):
        current = [i] + [0] * len(hypothesis)
        for j, hyp_word in enumerate(hypothesis, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ref_word != hyp_word))
        previous = current
    return previous[-1]


def gpu_memory_mb() -> int | None:
    try:
        output = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, check=True).stdout
        return int(output.split()[0])
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return None


def convert(hf_model: str) -> Path:
    """Convert a Hugging Face Whisper model (e.g. vinai/PhoWhisper-medium) to CTranslate2 once."""
    destination = CONVERTED_DIR / hf_model.replace("/", "--")
    if not (destination / "model.bin").exists():
        subprocess.run(["ct2-transformers-converter", "--model", hf_model, "--output_dir", str(destination),
                        "--copy_files", "tokenizer.json", "preprocessor_config.json",
                        "--quantization", "float16", "--force"], check=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="+")
    parser.add_argument("--convert", action="store_true", help="Treat models as Hugging Face ids to convert")
    parser.add_argument("--vad", action="store_true", help="Enable faster-whisper's VAD filter")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N clips")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    from app.core.config import get_settings

    settings = get_settings()
    clips = load_manifest()[: args.limit or None]
    audio_seconds = sum(_duration(c.path) for c in clips)
    print(f"{len(clips)} clips, {audio_seconds / 60:.1f} min of audio, device={settings.DEVICE} "
          f"compute={settings.COMPUTE_TYPE} vad={args.vad}\n")
    print("| Model | WER | Errors / words | Time (s) | Time / audio | GPU memory (MB) |")
    print("|---|---|---|---|---|---|")
    for name in args.models:
        source = str(convert(name)) if args.convert else name
        idle = gpu_memory_mb()
        model = WhisperModel(source, device=settings.DEVICE, compute_type=settings.COMPUTE_TYPE)
        errors = words = 0
        peak = 0
        started = time.perf_counter()
        for clip in clips:
            segments, _ = model.transcribe(str(clip.path), language="vi", vad_filter=args.vad)
            hypothesis = normalize(" ".join(s.text for s in segments))
            reference = normalize(clip.text)
            errors += word_errors(reference, hypothesis)
            words += len(reference)
            peak = max(peak, gpu_memory_mb() or 0)
        elapsed = time.perf_counter() - started
        memory = f"{peak - idle}" if idle is not None and peak else "–"
        print(f"| {name} | {errors / words:.1%} | {errors}/{words} | {elapsed:.0f} | {elapsed / audio_seconds:.3f} "
              f"| {memory} |", flush=True)
        del model
    return 0


def _duration(path: Path) -> float:
    # FLEURS clips are float32 WAV, which the wave module cannot read.
    from faster_whisper import decode_audio

    return len(decode_audio(str(path), sampling_rate=16000)) / 16000


if __name__ == "__main__":
    sys.exit(main())
