"""Measure gender recognition on real Vietnamese voices with known gender (FLEURS vi_vn, CC BY 4.0).

    docker compose run --rm -v "${PWD}:/app" api python -m scripts.eval_gender fetch --per-gender 60
    docker compose run --rm -v "${PWD}:/app" api python -m scripts.eval_gender clips
    docker compose run --rm -v "${PWD}:/app" api python -m scripts.eval_gender meetings --count 6

fetch     streams the FLEURS train archive (1.6 GB) and stops once it has extracted N clips per gender
          (the dev and test splits are all male). `--holdout` fetches other clips, in archive order,
          into a held-out set that is never used to pick settings.
clips     classifies each clip on its own: the gender model without diarization errors (`--holdout`
          for the held-out set).
meetings  joins clips of different genders into short synthetic meetings, runs the full pipeline and
          checks the gender given to the speaker covering each clip.
Clips go to sample_data/real/fleurs/ (not committed, not in the image).
"""
import argparse
import csv
import io
import random
import sys
import tarfile
import time
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path


BASE_URL = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/vi_vn"
DATA_DIR = Path("sample_data/real/fleurs")
# Clips never used to choose settings, to check that a tuned threshold holds on new voices.
HOLDOUT_DIR = Path("sample_data/real/fleurs_holdout")
MANIFEST_NAME = "manifest.tsv"
GENDERS = ("male", "female")
SILENCE_SECONDS = 0.8


@dataclass
class Clip:
    path: Path
    gender: str
    text: str


def select_balanced(rows: list[tuple[str, str, str]], per_gender: int, seed: int = 0) -> dict[str, tuple[str, str]]:
    """Pick up to `per_gender` distinct files per gender from (file_name, text, GENDER) rows.

    Returns {file_name: (gender, text)}. Chosen at random (seeded) so clips are not all one sentence.
    """
    by_gender: dict[str, list[tuple[str, str]]] = {g: [] for g in GENDERS}
    seen: set[str] = set()
    for file_name, text, gender in rows:
        gender = gender.lower()
        if gender in by_gender and file_name not in seen:
            seen.add(file_name)
            by_gender[gender].append((file_name, text))
    rng = random.Random(seed)
    chosen: dict[str, tuple[str, str]] = {}
    for gender, items in by_gender.items():
        for file_name, text in rng.sample(items, min(per_gender, len(items))):
            chosen[file_name] = (gender, text)
    return chosen


def _train_rows() -> list[tuple[str, str, str]]:
    """(file_name, raw transcription, GENDER) for every clip of the train split."""
    with urllib.request.urlopen(f"{BASE_URL}/train.tsv") as response:
        tsv = response.read().decode("utf-8")
    return [(r[1], r[2], r[6]) for r in csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)]


def _write_manifest(directory: Path, entries: dict[str, tuple[str, str]]) -> None:
    with (directory / MANIFEST_NAME).open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        for name, (gender, text) in sorted(entries.items()):
            if (directory / name).exists():
                writer.writerow([name, gender, text])


def fetch(per_gender: int) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    wanted = select_balanced(_train_rows(), per_gender)
    missing = {name for name in wanted if not (DATA_DIR / name).exists()}
    print(f"selected {len(wanted)} clips, {len(missing)} to download", file=sys.stderr)

    if missing:
        downloaded = 0
        with urllib.request.urlopen(f"{BASE_URL}/audio/train.tar.gz") as response:
            counting = _CountingReader(response)
            with tarfile.open(fileobj=counting, mode="r|gz") as archive:
                for member in archive:
                    name = Path(member.name).name
                    if name in missing and member.isfile():
                        (DATA_DIR / name).write_bytes(archive.extractfile(member).read())
                        missing.discard(name)
                        downloaded += 1
                    if not missing:
                        break
        print(f"extracted {downloaded} clips after {counting.bytes_read / 1e6:.0f} MB", file=sys.stderr)
    if missing:
        print(f"{len(missing)} clips not found in the archive", file=sys.stderr)

    _write_manifest(DATA_DIR, wanted)


def fetch_holdout(per_gender: int) -> None:
    """The first N clips per gender in archive order that are not in the main set (reads little of it)."""
    HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)
    used = {clip.path.name for clip in load_manifest()}
    labels = {name: (gender.lower(), text) for name, text, gender in _train_rows() if name not in used}
    taken: dict[str, tuple[str, str]] = {}
    counts = dict.fromkeys(GENDERS, 0)
    with urllib.request.urlopen(f"{BASE_URL}/audio/train.tar.gz") as response:
        counting = _CountingReader(response)
        with tarfile.open(fileobj=counting, mode="r|gz") as archive:
            for member in archive:
                name = Path(member.name).name
                gender = labels.get(name, ("", ""))[0]
                if member.isfile() and gender in counts and counts[gender] < per_gender:
                    (HOLDOUT_DIR / name).write_bytes(archive.extractfile(member).read())
                    taken[name] = labels[name]
                    counts[gender] += 1
                if all(count >= per_gender for count in counts.values()):
                    break
    print(f"extracted {counts} after {counting.bytes_read / 1e6:.0f} MB", file=sys.stderr)
    _write_manifest(HOLDOUT_DIR, taken)


class _CountingReader(io.RawIOBase):
    """File-like wrapper that counts the bytes read (to report how much of the archive was needed)."""

    def __init__(self, raw):
        self.raw, self.bytes_read = raw, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        data = self.raw.read(len(buffer))
        self.bytes_read += len(data)
        buffer[:len(data)] = data
        return len(data)


def load_manifest(directory: Path = DATA_DIR) -> list[Clip]:
    with (directory / MANIFEST_NAME).open(encoding="utf-8") as f:
        return [Clip(directory / name, gender, text) for name, gender, text in csv.reader(f, delimiter="\t")]


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def accuracy_table(results: list[tuple[str, str, float]]) -> str:
    """Markdown summary of (truth, predicted, confidence) triples: accuracy per gender and coverage
    when predictions below a confidence threshold become "unknown"."""
    lines = ["| Truth | Clips | Correct | Wrong | Unknown |", "|---|---|---|---|---|"]
    for gender in GENDERS:
        rows = [r for r in results if r[0] == gender]
        correct = sum(r[1] == gender for r in rows)
        unknown = sum(r[1] not in GENDERS for r in rows)
        lines.append(f"| {gender} | {len(rows)} | {correct} | {len(rows) - correct - unknown} | {unknown} |")
    lines += ["", "| Min confidence | Answered | Accuracy of answered |", "|---|---|---|"]
    for threshold in (0.0, 0.6, 0.7, 0.8, 0.9):
        answered = [r for r in results if r[1] in GENDERS and r[2] >= threshold]
        correct = sum(r[0] == r[1] for r in answered)
        rate = f"{correct / len(answered):.1%}" if answered else "–"
        lines.append(f"| {threshold:.1f} | {len(answered)}/{len(results)} | {rate} |")
    return "\n".join(lines)


def run_clips(directory: Path) -> None:
    from app.models.schemas import SpeakerSegment
    from app.services.audio_preprocessing import preprocess_audio
    from app.services.gender import get_gender_pipeline, predict_speakers_gender

    get_gender_pipeline()
    results = []
    started = time.perf_counter()
    for clip in load_manifest(directory):
        normalized =Path(preprocess_audio(clip.path).normalized_path)
        try:
            segment = SpeakerSegment(speaker="S", start=0.0, end=_duration(normalized))
            prediction = predict_speakers_gender(normalized, [segment])["S"]
        finally:
            normalized.unlink(missing_ok=True)
        results.append((clip.gender, prediction.gender, prediction.confidence))
    print(f"{len(results)} clips in {time.perf_counter() - started:.1f}s\n")
    print(accuracy_table(results))


def build_meeting(clips: list[Clip], destination: Path, gap: float = SILENCE_SECONDS) -> list[tuple[float, float, str]]:
    """Concatenate 16 kHz mono clips with `gap` seconds of silence; return (start, end, gender) per clip."""
    from pydub import AudioSegment

    audio = AudioSegment.silent(duration=int(SILENCE_SECONDS * 1000), frame_rate=16000)
    spans = []
    for clip in clips:
        part = AudioSegment.from_wav(clip.path).set_frame_rate(16000).set_channels(1)
        start = len(audio) / 1000
        audio += part
        spans.append((start, len(audio) / 1000, clip.gender))
        audio += AudioSegment.silent(duration=int(gap * 1000), frame_rate=16000)
    audio.export(destination, format="wav")
    return spans


def speaker_for_span(turns: list[tuple[float, float, str]], start: float, end: float) -> str | None:
    """Speaker label of the turns overlapping [start, end] the most."""
    overlap: dict[str, float] = {}
    for turn_start, turn_end, speaker in turns:
        shared = min(end, turn_end) - max(start, turn_start)
        if shared > 0:
            overlap[speaker] = overlap.get(speaker, 0.0) + shared
    return max(overlap, key=overlap.get) if overlap else None


def mixed_utterances(utterances: list[tuple[float, float, str]], spans: list[tuple[float, float, str]],
                     tolerance: float = 0.3) -> int:
    """Utterances that contain more than `tolerance` seconds of two or more different clips (speakers)."""
    mixed = 0
    for start, end, _ in utterances:
        touched = sum(min(end, span_end) - max(start, span_start) > tolerance for span_start, span_end, _ in spans)
        mixed += touched > 1
    return mixed


def attribution_accuracy(utterances: list[tuple[float, float, str]], spans: list[tuple[float, float, str]]) -> float:
    """Share of transcribed speech (by time) labelled with the speaker that holds most of its clip."""
    right = total = 0.0
    for span_start, span_end, _ in spans:
        owner = speaker_for_span(utterances, span_start, span_end)
        for start, end, speaker in utterances:
            shared = min(end, span_end) - max(start, span_start)
            if shared > 0:
                total += shared
                right += shared if speaker == owner else 0.0
    return right / total if total else 0.0


def run_meetings(count: int, speakers_per_meeting: int, gap: float) -> None:
    from app.services.pipeline import analyze_meeting

    clips = load_manifest()
    by_gender = {g: [c for c in clips if c.gender == g] for g in GENDERS}
    rng = random.Random(1)
    results = []
    out_dir = DATA_DIR / "meetings"
    out_dir.mkdir(exist_ok=True)
    print(f"gap between speakers: {gap}s\n")
    print("| Meeting | Clips (M/F) | Speakers found | Gender correct | Mixed utterances | Attribution |")
    print("|---|---|---|---|---|---|")
    mixed_total = utterance_total = 0
    attribution_scores = []
    for index in range(count):
        half = speakers_per_meeting // 2
        chosen = rng.sample(by_gender["male"], half) + rng.sample(by_gender["female"], speakers_per_meeting - half)
        rng.shuffle(chosen)
        path = out_dir / f"meeting_{index}.wav"
        spans = build_meeting(chosen, path, gap)
        result = analyze_meeting(path)
        turns = [(t.start, t.end, t.speaker) for t in result.segments]
        gender_of = {t.speaker: (t.gender, t.gender_confidence) for t in result.segments}
        utterances = [(u.start, u.end, t.speaker) for t in result.segments for u in t.utterances]
        mixed = mixed_utterances(utterances, spans)
        attribution = attribution_accuracy(utterances, spans)
        mixed_total += mixed
        utterance_total += len(utterances)
        attribution_scores.append(attribution)
        correct = 0
        for start, end, truth in spans:
            speaker = speaker_for_span(turns, start, end)
            predicted, confidence = gender_of.get(speaker, ("unknown", 0.0))
            results.append((truth, predicted, confidence))
            correct += predicted == truth
        print(f"| {path.name} | {half}/{speakers_per_meeting - half} | {result.speaker_count} "
              f"| {correct}/{len(spans)} | {mixed}/{len(utterances)} | {attribution:.1%} |", flush=True)
    print(f"\nMixed utterances: {mixed_total}/{utterance_total}; "
          f"mean attribution: {sum(attribution_scores) / len(attribution_scores):.1%}\n")
    print(accuracy_table(results))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("--per-gender", type=int, default=60)
    fetch_parser.add_argument("--holdout", action="store_true", help="Fetch new clips into the held-out set")
    clips_parser = commands.add_parser("clips")
    clips_parser.add_argument("--holdout", action="store_true", help="Use the held-out set")
    meetings_parser = commands.add_parser("meetings")
    meetings_parser.add_argument("--count", type=int, default=6)
    meetings_parser.add_argument("--speakers", type=int, default=4)
    meetings_parser.add_argument("--gap", type=float, default=SILENCE_SECONDS, help="Silence between speakers (s)")
    args = parser.parse_args()

    if args.command == "fetch":
        (fetch_holdout if args.holdout else fetch)(args.per_gender)
    elif args.command == "clips":
        run_clips(HOLDOUT_DIR if args.holdout else DATA_DIR)
    else:
        run_meetings(args.count, args.speakers, args.gap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
