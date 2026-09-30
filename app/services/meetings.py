"""Meeting records: upload, listing, retry and deletion. Independent of HTTP."""
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Meeting, MeetingStatus
from app.storage.base import Storage

logger = logging.getLogger(__name__)

CONTENT_TYPES: dict[str, str] = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}
MAX_FILENAME_LENGTH = 255


class MeetingError(Exception):
    pass


class InvalidUploadError(MeetingError):
    pass


class MeetingNotFoundError(MeetingError):
    pass


class MeetingStateError(MeetingError):
    """The operation is not allowed in the meeting's current status."""


@dataclass
class Upload:
    filename: str
    fileobj: BinaryIO
    size: int


def _validate(upload: Upload, max_bytes: int) -> str:
    """Return the lowercase extension of a valid upload."""
    ext = Path(upload.filename).suffix.lower()
    if ext not in CONTENT_TYPES:
        raise InvalidUploadError(
            f"'{upload.filename}': unsupported format. Supported: {', '.join(sorted(CONTENT_TYPES))}"
        )
    if upload.size == 0:
        raise InvalidUploadError(f"'{upload.filename}': file is empty")
    if upload.size > max_bytes:
        raise InvalidUploadError(f"'{upload.filename}': file exceeds {max_bytes // (1024 * 1024)} MB")
    return ext


def create_meetings(session: Session, storage: Storage, uploads: list[Upload], max_bytes: int) -> list[Meeting]:
    """Store every original recording and queue one job per file.

    All files are validated before anything is stored; on any failure the objects already
    uploaded are removed and no meeting is created.
    """
    if not uploads:
        raise InvalidUploadError("No files uploaded")
    extensions = [_validate(upload, max_bytes) for upload in uploads]

    meetings: list[Meeting] = []
    try:
        for upload, ext in zip(uploads, extensions):
            meeting_id = uuid.uuid4()
            meeting = Meeting(
                id=meeting_id,
                filename=Path(upload.filename).name[:MAX_FILENAME_LENGTH],
                content_type=CONTENT_TYPES[ext],
                size_bytes=upload.size,
                storage_key=f"meetings/{meeting_id}/original{ext}",
                status=MeetingStatus.queued,
            )
            storage.upload(meeting.storage_key, upload.fileobj, meeting.content_type)
            meetings.append(meeting)
        session.add_all(meetings)
        session.commit()
    except Exception:
        session.rollback()
        for meeting in meetings:
            try:
                storage.delete(meeting.storage_key)
            except Exception:
                logger.exception("Could not remove orphaned object %s", meeting.storage_key)
        raise
    return meetings


def list_meetings(
    session: Session, status: MeetingStatus | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[Meeting], int]:
    """Newest first, with the total count for pagination."""
    query = select(Meeting)
    if status is not None:
        query = query.where(Meeting.status == status)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(query.order_by(Meeting.seq.desc()).limit(limit).offset(offset)).all()
    return list(items), total


def get_meeting(session: Session, meeting_id: uuid.UUID, for_update: bool = False) -> Meeting:
    meeting = session.get(Meeting, meeting_id, with_for_update=for_update)
    if meeting is None:
        raise MeetingNotFoundError(f"Meeting {meeting_id} not found")
    return meeting


def retry_meeting(session: Session, meeting_id: uuid.UUID) -> Meeting:
    """Put a failed meeting back in the queue."""
    meeting = get_meeting(session, meeting_id, for_update=True)
    if meeting.status != MeetingStatus.failed:
        session.rollback()
        raise MeetingStateError(f"Only failed meetings can be retried (status: {meeting.status.value})")
    meeting.status = MeetingStatus.queued
    meeting.current_stage = None
    meeting.error_code = None
    meeting.error_message = None
    meeting.started_at = None
    meeting.finished_at = None
    session.commit()
    return meeting


def delete_meeting(session: Session, storage: Storage, meeting_id: uuid.UUID) -> None:
    """Delete the recording and every result. A meeting being processed cannot be deleted."""
    # The row lock waits for a worker that is claiming this meeting, so its status is current.
    meeting = get_meeting(session, meeting_id, for_update=True)
    if meeting.status == MeetingStatus.processing:
        session.rollback()
        raise MeetingStateError("Meeting is being processed; delete it after it finishes")
    storage.delete(meeting.storage_key)
    session.delete(meeting)
    session.commit()
