"""Job queue on the meetings table: claim with SKIP LOCKED, run the pipeline, store the result."""
import logging
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Meeting, MeetingStatus, Segment, Speaker
from app.models.schemas import MeetingAnalysisResult
from app.services.pipeline import StageCallback
from app.storage.base import Storage

logger = logging.getLogger(__name__)

Analyzer = Callable[[Path, StageCallback], MeetingAnalysisResult]
MAX_ERROR_LENGTH = 2000


def claim_next(session: Session) -> uuid.UUID | None:
    """Mark the oldest queued meeting as processing and return its id.

    SKIP LOCKED lets several workers poll at once without taking the same job.
    """
    meeting = session.scalars(
        select(Meeting)
        .where(Meeting.status == MeetingStatus.queued)
        .order_by(Meeting.seq)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if meeting is None:
        session.rollback()
        return None
    meeting.status = MeetingStatus.processing
    meeting.current_stage = "downloading"
    meeting.attempts += 1
    meeting.started_at = func.now()
    meeting.finished_at = None
    session.commit()
    return meeting.id


def requeue_interrupted(session: Session) -> int:
    """Put meetings left in `processing` by a stopped worker back in the queue.

    Only safe while a single worker runs, which is how compose deploys it.
    """
    result = session.execute(
        update(Meeting)
        .where(Meeting.status == MeetingStatus.processing)
        .values(status=MeetingStatus.queued, current_stage=None)
    )
    session.commit()
    return result.rowcount


def _set_stage(sessions: sessionmaker[Session], meeting_id: uuid.UUID, stage: str) -> None:
    with sessions() as session:
        session.execute(update(Meeting).where(Meeting.id == meeting_id).values(current_stage=stage))
        session.commit()


def _save_result(session: Session, meeting: Meeting, result: MeetingAnalysisResult) -> None:
    speakers: dict[str, Speaker] = {}
    for turn in result.segments:
        if turn.speaker not in speakers:
            speakers[turn.speaker] = Speaker(
                label=turn.speaker,
                display_name=turn.speaker,
                gender=turn.gender,
                gender_confidence=turn.gender_confidence,
            )
    meeting.speakers.extend(speakers[label] for label in sorted(speakers))
    meeting.segments.extend(
        Segment(
            speaker=speakers[turn.speaker],
            start=turn.start,
            end=turn.end,
            text=turn.text,
            sentiment=turn.sentiment,
            sentiment_confidence=turn.sentiment_confidence,
        )
        for turn in result.segments
    )
    meeting.duration_seconds = result.duration
    meeting.speaker_count = result.speaker_count
    meeting.status = MeetingStatus.done
    meeting.current_stage = None
    meeting.finished_at = func.now()


def _mark_failed(session: Session, meeting_id: uuid.UUID, exc: Exception) -> None:
    session.execute(
        update(Meeting)
        .where(Meeting.id == meeting_id)
        .values(
            status=MeetingStatus.failed,
            current_stage=None,
            error_code=type(exc).__name__,
            error_message=str(exc)[:MAX_ERROR_LENGTH],
            finished_at=func.now(),
        )
    )
    session.commit()


def process_next(sessions: sessionmaker[Session], storage: Storage, analyze: Analyzer, temp_dir: Path) -> bool:
    """Run one queued meeting to completion. Returns False when the queue is empty."""
    with sessions() as session:
        meeting_id = claim_next(session)
    if meeting_id is None:
        return False

    logger.info("Processing meeting %s", meeting_id)
    try:
        with sessions() as session:
            storage_key = session.get(Meeting, meeting_id).storage_key
        temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_dir) as work_dir:
            audio_path = Path(work_dir) / f"original{Path(storage_key).suffix}"
            storage.download(storage_key, audio_path)
            result = analyze(audio_path, lambda stage: _set_stage(sessions, meeting_id, stage))
        with sessions() as session:
            _save_result(session, session.get(Meeting, meeting_id), result)
            session.commit()
    except Exception as exc:
        logger.exception("Meeting %s failed", meeting_id)
        with sessions() as session:
            _mark_failed(session, meeting_id, exc)
    else:
        logger.info("Meeting %s done", meeting_id)
    return True
