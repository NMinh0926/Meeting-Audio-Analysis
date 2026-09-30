"""Meeting endpoints: upload recordings, follow their jobs, retry and delete."""
import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, FastAPI, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MeetingStatus
from app.db.session import get_db
from app.models.schemas import MeetingDetail, MeetingList, MeetingOut
from app.services import meetings as service
from app.storage.base import Storage
from app.storage.s3 import S3Storage, StorageError

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
    StorageError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def register_error_handlers(app: FastAPI) -> None:
    """Map service errors to HTTP responses."""
    for error, code in _ERROR_STATUS.items():
        def handler(request: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse(status_code=code, content={"detail": str(exc)})

        app.add_exception_handler(error, handler)
