"""Background worker: runs queued meetings through the pipeline, one at a time.

    python -m app.worker

Models load on the first job and stay in memory for the next ones.
"""
import logging
import signal
import threading
from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.services.jobs import process_next, requeue_interrupted
from app.services.pipeline import analyze_meeting
from app.storage.s3 import S3Storage

logger = logging.getLogger("app.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    settings = get_settings()
    sessions = get_sessionmaker()
    storage = S3Storage.from_settings(settings)

    stopping = threading.Event()
    # docker stop sends SIGTERM: stop after the current job. If the grace period ends first,
    # the job stays `processing` and requeue_interrupted picks it up on the next start.
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())

    with sessions() as session:
        requeued = requeue_interrupted(session)
    if requeued:
        logger.info("Requeued %d interrupted meeting(s)", requeued)

    logger.info("Worker started (device=%s, whisper=%s)", settings.DEVICE, settings.WHISPER_MODEL)
    while not stopping.is_set():
        if not process_next(sessions, storage, analyze_meeting, Path(settings.TEMP_DIR)):
            stopping.wait(settings.WORKER_POLL_SECONDS)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
