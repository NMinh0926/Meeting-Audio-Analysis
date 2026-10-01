"""Recompute the emotion of every turn of processed meetings with the current emotion models.

    docker compose stop worker
    docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.recompute_emotions [MEETING_ID…]

Without ids, every meeting with status `done` is updated. Transcripts, speakers and genders are kept;
only each turn's emotion and confidence change. Stop the worker first so the GPU is free.
"""
import argparse
import logging
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Meeting, MeetingStatus, Segment
from app.models.schemas import PreprocessingResult, SentimentResult, SpeakerTurn, TranscriptSegment
from app.storage.base import Storage

logger = logging.getLogger("scripts.recompute_emotions")

Predict = Callable[[Path, Sequence[SpeakerTurn]], list[SentimentResult]]
Preprocess = Callable[[Path], PreprocessingResult]


def _turn(segment: Segment) -> SpeakerTurn:
    return SpeakerTurn(
        speaker=str(segment.speaker_id), start=segment.start, end=segment.end, text=segment.text,
        utterances=[TranscriptSegment(start=u.start, end=u.end, text=u.text) for u in segment.utterances],
    )


def recompute_meeting(session: Session, storage: Storage, meeting: Meeting, temp_dir: Path,
                      predict: Predict, preprocess: Preprocess) -> int:
    """Re-run emotion on one meeting's turns and save it; returns how many turns changed emotion."""
    with tempfile.TemporaryDirectory(dir=temp_dir) as work:
        original = Path(work) / f"original{Path(meeting.storage_key).suffix}"
        storage.download(meeting.storage_key, original)
        normalized = Path(preprocess(original).normalized_path)
        try:
            results = predict(normalized, [_turn(s) for s in meeting.segments])
        finally:
            normalized.unlink(missing_ok=True)
    changed = 0
    for segment, result in zip(meeting.segments, results, strict=True):
        changed += segment.sentiment != result.sentiment
        segment.sentiment = result.sentiment
        segment.sentiment_confidence = result.confidence
    session.commit()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", type=uuid.UUID)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from app.core.config import get_settings
    from app.db.session import get_sessionmaker
    from app.services.audio_preprocessing import preprocess_audio
    from app.services.emotion import predict_turn_emotions
    from app.storage.s3 import S3Storage

    settings = get_settings()
    storage = S3Storage.from_settings(settings)
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    query = (select(Meeting).where(Meeting.status == MeetingStatus.done)
             .options(selectinload(Meeting.segments).selectinload(Segment.utterances)).order_by(Meeting.seq))
    if args.ids:
        query = query.where(Meeting.id.in_(args.ids))
    with get_sessionmaker()() as session:
        for meeting in session.scalars(query).all():
            changed = recompute_meeting(session, storage, meeting, temp_dir, predict_turn_emotions, preprocess_audio)
            logger.info("%s: %d/%d turns changed emotion", meeting.filename, changed, len(meeting.segments))
    return 0


if __name__ == "__main__":
    sys.exit(main())
