"""Compare Whisper decoding options on real recordings: speech left without words, speed, FLEURS WER.

    docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.bench_transcript \
        sample_data/real/life_abroad_ep8.mp3 --variants current,prompt [--model large-v3] [--fleurs]

Conversational recordings have no reference text, so missed speech is measured against diarization:
seconds pyannote marks as speech that no transcribed word comes near. Diarization runs once per file
and is cached next to the transcripts in `sample_data/real/coverage/`. Stop the worker first.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from scripts.bench_asr import normalize, word_errors
from scripts.eval_gender import load_manifest

OUT_DIR = Path("sample_data/real/coverage")
# Word timestamps are approximate; speech this close to a word counts as transcribed.
WORD_TOLERANCE_SECONDS = 0.3
REPORTED_GAP_SECONDS = 2.0
PROMPT = "Xin chào. Sau đây là cuộc trò chuyện bằng tiếng Việt, có đầy đủ dấu câu."

BASE = {"word_timestamps": True, "condition_on_previous_text": False}
VARIANTS: dict[str, dict] = {
    "current": {**BASE, "hallucination_silence_threshold": 2.0},
    "silence4": {**BASE, "hallucination_silence_threshold": 4.0},
    "prompt": {**BASE, "hallucination_silence_threshold": 2.0, "initial_prompt": PROMPT},
}

Span = tuple[float, float]


def merge(spans: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def uncovered(speech: list[Span], covered: list[Span]) -> list[Span]:
    """Parts of `speech` outside every `covered` span (both lists merged and sorted)."""
    gaps: list[Span] = []
    j = 0
    for start, end in speech:
        cursor = start
        while j < len(covered) and covered[j][1] <= cursor:
            j += 1
        k = j
        while k < len(covered) and covered[k][0] < end:
            if covered[k][0] > cursor:
                gaps.append((cursor, covered[k][0]))
            cursor = max(cursor, covered[k][1])
            k += 1
        if cursor < end:
            gaps.append((cursor, end))
    return gaps


def speech_spans(normalized: Path, cache: Path) -> list[Span]:
    if not cache.exists():
        from app.core.gpu import release_cached_memory
        from app.services.diarization import diarize_audio

        segments = diarize_audio(normalized)
        release_cached_memory()
        cache.write_text(json.dumps([[s.start, s.end] for s in segments]), encoding="utf-8")
    return merge([(s, e) for s, e in json.loads(cache.read_text(encoding="utf-8"))])


def fleurs_wer(model, options: dict) -> float:
    errors = words = 0
    for clip in load_manifest():
        segments, _ = model.transcribe(str(clip.path), language="vi", **options)
        reference = normalize(clip.text)
        errors += word_errors(reference, normalize(" ".join(s.text for s in segments)))
        words += len(reference)
    return errors / words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--variants", default="current", help=f"Comma separated: {', '.join(VARIANTS)}")
    parser.add_argument("--fleurs", action="store_true", help="Also measure WER on the FLEURS clips")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    from app.core.config import get_settings
    from app.services.audio_preprocessing import preprocess_audio

    settings = get_settings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = []
    for path in args.files:
        normalized = Path(preprocess_audio(path).normalized_path)
        inputs.append((path, normalized, speech_spans(normalized, OUT_DIR / f"{path.stem}.diarization.json")))

    model = WhisperModel(args.model, device=settings.DEVICE, compute_type=settings.COMPUTE_TYPE)
    print("| Model | Variant | File | Speech (s) | Missed (s) | Missed % | Gaps ≥ 2 s | Time (s) |")
    print("|---|---|---|---|---|---|---|---|")
    try:
        for variant in args.variants.split(","):
            options = VARIANTS[variant]
            for path, normalized, speech in inputs:
                started = time.perf_counter()
                segments = list(model.transcribe(str(normalized), language=settings.WHISPER_LANGUAGE, **options)[0])
                elapsed = time.perf_counter() - started
                words = [w for s in segments for w in (s.words or [])]
                covered = merge([(w.start - WORD_TOLERANCE_SECONDS, w.end + WORD_TOLERANCE_SECONDS) for w in words])
                gaps = uncovered(speech, covered)
                speech_total = sum(e - s for s, e in speech)
                missed = sum(e - s for s, e in gaps)
                long_gaps = [(round(s, 1), round(e, 1)) for s, e in gaps if e - s >= REPORTED_GAP_SECONDS]
                print(f"| {args.model} | {variant} | {path.name} | {speech_total:.0f} | {missed:.1f} "
                      f"| {missed / speech_total:.1%} | {len(long_gaps)} | {elapsed:.0f} |", flush=True)
                out = OUT_DIR / f"{path.stem}.{args.model}.{variant}.json"
                out.write_text(json.dumps({
                    "gaps": long_gaps,
                    "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments],
                }, ensure_ascii=False, indent=1), encoding="utf-8")
            if args.fleurs:
                print(f"| {args.model} | {variant} | FLEURS WER {fleurs_wer(model, options):.1%} | | | | | |", flush=True)
    finally:
        for _, normalized, _ in inputs:
            normalized.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
