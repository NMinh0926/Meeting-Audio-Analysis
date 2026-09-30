"""Time gender classification alone on processed meetings, reusing their stored turns as speaker segments.

    docker compose run --rm -v "${PWD}:/app" api python -m scripts.bench_gender

For each `done` meeting: download the original, normalize it, feed the stored speaker turns to
predict_speakers_gender and print the time and the result per speaker next to the stored result.
Run it while the worker is idle so the GPU is not shared.
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import Meeting, MeetingStatus
from app.db.session import get_sessionmaker
from app.models.schemas import SpeakerSegment
from app.services.audio_preprocessing import preprocess_audio
from app.services.gender import get_gender_pipeline, predict_speakers_gender
from app.storage.s3 import S3Storage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filename", action="append", help="Only these meetings (repeatable)")
    args = parser.parse_args()

    settings = get_settings()
    storage = S3Storage.from_settings(settings)
    with get_sessionmaker()() as session:
        query = select(Meeting).where(Meeting.status == MeetingStatus.done).order_by(Meeting.seq)
        if args.filename:
            query = query.where(Meeting.filename.in_(args.filename))
        meetings = session.scalars(query.options(selectinload(Meeting.segments), selectinload(Meeting.speakers))).all()
        jobs = [
            (m.filename, m.duration_seconds, m.storage_key,
             [SpeakerSegment(speaker=s.speaker.label, start=s.start, end=s.end) for s in m.segments],
             {sp.label: (sp.gender, sp.gender_confidence) for sp in m.speakers})
            for m in meetings
        ]

    started = time.perf_counter()
    get_gender_pipeline()
    print(f"model load: {time.perf_counter() - started:.1f}s (device={settings.DEVICE})", file=sys.stderr)

    print("| File | Audio (s) | Turns | Gender (s) | Result (stored → now) |")
    print("|---|---|---|---|---|")
    for filename, duration, key, segments, stored in jobs:
        with tempfile.TemporaryDirectory(dir=settings.TEMP_DIR) as work_dir:
            original = Path(work_dir) / f"original{Path(key).suffix}"
            storage.download(key, original)
            normalized = Path(preprocess_audio(original).normalized_path)
            try:
                started = time.perf_counter()
                result = predict_speakers_gender(normalized, segments)
                elapsed = time.perf_counter() - started
            finally:
                normalized.unlink(missing_ok=True)
        changes = ", ".join(
            f"{label}: {stored[label][0]} {stored[label][1]:.2f} → {r.gender} {r.confidence:.2f}"
            for label, r in sorted(result.items())
        )
        print(f"| {filename} | {duration:.0f} | {len(segments)} | {elapsed:.1f} | {changes} |", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
