"""Meeting endpoints: upload recordings, follow their jobs, review transcripts, retry and delete."""
import unicodedata
import uuid
from pathlib import Path
from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, FastAPI, Header, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.byte_range import RangeNotSatisfiableError, parse_range
from app.core.config import get_settings
from app.db.models import MeetingStatus
from app.db.session import get_db
from app.models.schemas import MeetingDetail, MeetingList, MeetingOut, SpeakerOut, SpeakerRename, TranscriptOut
from app.services import meetings as service
from app.services.export import ExportFormat, export_transcript
from app.storage.base import Storage
from app.storage.s3 import ObjectNotFoundError, S3Storage, StorageError

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@lru_cache
def get_storage() -> Storage:
    return S3Storage.from_settings(get_settings())


DbSession = Annotated[Session, Depends(get_db)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def _file_size(upload: UploadFile) -> int:
    if upload.size is not None:
        return upload.size
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=list[MeetingOut])
def upload_meetings(
    db: DbSession, storage: StorageDep, files: Annotated[list[UploadFile], File(description="WAV/MP3/M4A")]
):
    """Store one or more recordings and queue a processing job for each."""
    uploads = [service.Upload(f.filename or "", f.file, _file_size(f)) for f in files]
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    return service.create_meetings(db, storage, uploads, max_bytes)


@router.get("", response_model=MeetingList)
def list_meetings(
    db: DbSession,
    status_filter: Annotated[MeetingStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Meetings newest first."""
    items, total = service.list_meetings(db, status_filter, limit, offset)
    return MeetingList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(db: DbSession, meeting_id: uuid.UUID):
    """Meeting status (current pipeline stage while processing) and its speakers."""
    return service.get_meeting(db, meeting_id)


@router.get("/{meeting_id}/transcript", response_model=TranscriptOut)
def get_transcript(db: DbSession, meeting_id: uuid.UUID):
    """Speakers and turns in time order, each turn with its utterances (for seeking and highlighting)."""
    meeting = service.get_transcript(db, meeting_id)
    return TranscriptOut(meeting_id=meeting.id, filename=meeting.filename, duration_seconds=meeting.duration_seconds,
                         speakers=meeting.speakers, turns=meeting.segments)


@router.get("/{meeting_id}/audio", response_class=StreamingResponse,
            responses={206: {"description": "Partial content"}, 416: {"description": "Range not satisfiable"}})
def get_audio(
    db: DbSession, storage: StorageDep, meeting_id: uuid.UUID,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    """The original recording. Supports `Range: bytes=…` so players can seek without downloading it all."""
    meeting = service.get_meeting(db, meeting_id)
    size = meeting.size_bytes
    try:
        byte_range = parse_range(range_header, size)
    except RangeNotSatisfiableError:
        return Response(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                        headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})

    start, end = byte_range or (0, size - 1)
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if byte_range is not None:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        storage.stream(meeting.storage_key, start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT if byte_range else status.HTTP_200_OK,
        media_type=meeting.content_type,
        headers=headers,
    )


def _content_disposition(filename: str) -> str:
    """Attachment header with an ASCII fallback and the UTF-8 name (RFC 6266 / 5987) for Vietnamese titles."""
    path = Path(filename)
    stem = unicodedata.normalize("NFKD", path.stem.replace("đ", "d").replace("Đ", "D"))
    ascii_stem = "".join(c for c in stem if c.isascii() and c.isprintable() and c not in '"\\') or "transcript"
    return f"attachment; filename=\"{ascii_stem}{path.suffix}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("/{meeting_id}/export", response_class=Response)
def export_meeting(
    db: DbSession, meeting_id: uuid.UUID, export_format: Annotated[ExportFormat, Query(alias="format")],
) -> Response:
    """Download the transcript as text (`txt`), subtitles (`srt`) or all extracted data (`json`)."""
    meeting = service.get_transcript(db, meeting_id)
    content, media_type, filename = export_transcript(meeting, export_format)
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": _content_disposition(filename)})


@router.patch("/{meeting_id}/speakers/{speaker_id}", response_model=SpeakerOut)
def rename_speaker(db: DbSession, meeting_id: uuid.UUID, speaker_id: int, body: SpeakerRename):
    """Change the name shown for a speaker in the transcript and exports."""
    return service.rename_speaker(db, meeting_id, speaker_id, body.display_name)


@router.post("/{meeting_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=MeetingOut)
def retry_meeting(db: DbSession, meeting_id: uuid.UUID):
    """Queue a failed meeting again."""
    return service.retry_meeting(db, meeting_id)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(db: DbSession, storage: StorageDep, meeting_id: uuid.UUID) -> None:
    """Delete the recording and all results. Not allowed while the meeting is processing."""
    service.delete_meeting(db, storage, meeting_id)


_ERROR_STATUS: dict[type[Exception], int] = {
    service.InvalidUploadError: status.HTTP_400_BAD_REQUEST,
    service.MeetingNotFoundError: status.HTTP_404_NOT_FOUND,
    service.MeetingStateError: status.HTTP_409_CONFLICT,
    ObjectNotFoundError: status.HTTP_404_NOT_FOUND,
    StorageError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def register_error_handlers(app: FastAPI) -> None:
    """Map service errors to HTTP responses."""
    for error, code in _ERROR_STATUS.items():
        def handler(request: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse(status_code=code, content={"detail": str(exc)})

        app.add_exception_handler(error, handler)
