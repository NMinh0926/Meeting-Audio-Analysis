"""Tests for the job queue and worker loop (PostgreSQL test database, fake pipeline)."""
import io
from pathlib import Path

from sqlalchemy import select

from app.db.models import Meeting, MeetingStatus
from app.models.schemas import FinalTurn, MeetingAnalysisResult
from app.services import meetings as meeting_service
from app.services.jobs import claim_next, process_next, requeue_interrupted

MAX_BYTES = 10 * 1024 * 1024


def _turn(speaker: str, start: float, text: str, gender: str = "male") -> FinalTurn:
    return FinalTurn(speaker=speaker, gender=gender, gender_confidence=0.9, sentiment="neutral",
                     sentiment_confidence=0.6, start=start, end=start + 1.0, text=text)


class FakeAnalyzer:
    """Stands in for analyze_meeting: reports stages and returns a fixed two-speaker result."""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls: list[tuple[str, bytes]] = []

    def __call__(self, audio_path: Path, on_stage) -> MeetingAnalysisResult:
        self.calls.append((audio_path.name, audio_path.read_bytes()))
        on_stage("transcription")
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("model exploded")
        return MeetingAnalysisResult(
            filename=audio_path.name, duration=12.5, speaker_count=2,
            segments=[_turn("SPEAKER_01", 0.0, "Chào mọi người", "female"),
                      _turn("SPEAKER_00", 2.0, "Bắt đầu họp"),
                      _turn("SPEAKER_01", 4.0, "Đồng ý", "female")],
        )


def _queue(sessions, storage, *names: str) -> list[Meeting]:
    uploads = [meeting_service.Upload(name, io.BytesIO(f"audio:{name}".encode()), 10) for name in names]
    with sessions() as session:
        return meeting_service.create_meetings(session, storage, uploads, MAX_BYTES)


def _reload(sessions, meeting_id) -> Meeting:
    with sessions() as session:
        meeting = session.get(Meeting, meeting_id)
        # Load relationships before the session closes.
        _ = meeting.speakers, [segment.speaker for segment in meeting.segments]
        return meeting


def _drain(sessions, storage, analyze, temp_dir: Path) -> int:
    runs = 0
    while process_next(sessions, storage, analyze, temp_dir):
        runs += 1
    return runs


def test_claim_takes_oldest_queued_meeting(sessions, storage):
    first, second = _queue(sessions, storage, "1.wav", "2.wav")

    with sessions() as session:
        assert claim_next(session) == first.id
    with sessions() as session:
        assert claim_next(session) == second.id
    with sessions() as session:
        assert claim_next(session) is None

    claimed = _reload(sessions, first.id)
    assert claimed.status == MeetingStatus.processing
    assert claimed.attempts == 1
    assert claimed.started_at is not None


def test_concurrent_claims_skip_locked_rows(sessions, storage):
    first, second = _queue(sessions, storage, "1.wav", "2.wav")

    # Another worker holds the lock on the oldest meeting mid-claim.
    with sessions() as holder:
        holder.execute(select(Meeting).where(Meeting.id == first.id).with_for_update())
        with sessions() as session:
            assert claim_next(session) == second.id
        holder.rollback()

    assert _reload(sessions, first.id).status == MeetingStatus.queued


def test_five_uploads_all_finish(sessions, storage, tmp_path):
    names = [f"meeting_{i}.mp3" for i in range(5)]
    meetings = _queue(sessions, storage, *names)
    analyzer = FakeAnalyzer()

    assert _drain(sessions, storage, analyzer, tmp_path) == 5

    # Oldest first, each with its own recording, downloaded under its original extension.
    assert [content for _, content in analyzer.calls] == [f"audio:{n}".encode() for n in names]
    assert {name for name, _ in analyzer.calls} == {"original.mp3"}
    for meeting in meetings:
        done = _reload(sessions, meeting.id)
        assert done.status == MeetingStatus.done
        assert done.current_stage is None
        assert done.finished_at is not None
        assert done.duration_seconds == 12.5
        assert done.speaker_count == 2
        assert [(s.label, s.gender) for s in done.speakers] == [("SPEAKER_00", "male"), ("SPEAKER_01", "female")]
        assert [(s.speaker.label, s.text) for s in done.segments] == [
            ("SPEAKER_01", "Chào mọi người"), ("SPEAKER_00", "Bắt đầu họp"), ("SPEAKER_01", "Đồng ý")]
    # Work files are removed after each job.
    assert list(tmp_path.iterdir()) == []


def test_stage_updates_are_visible_while_running(sessions, storage, tmp_path):
    (meeting,) = _queue(sessions, storage, "a.wav")
    seen: list[str | None] = []

    def analyze(audio_path: Path, on_stage) -> MeetingAnalysisResult:
        on_stage("diarization")
        seen.append(_reload(sessions, meeting.id).current_stage)
        return FakeAnalyzer()(audio_path, lambda stage: None)

    process_next(sessions, storage, analyze, tmp_path)

    assert seen == ["diarization"]
    assert _reload(sessions, meeting.id).current_stage is None


def test_failed_job_records_error_and_can_be_retried(sessions, storage, tmp_path):
    (meeting,) = _queue(sessions, storage, "a.wav")
    analyzer = FakeAnalyzer(fail_times=1)

    assert _drain(sessions, storage, analyzer, tmp_path) == 1
    failed = _reload(sessions, meeting.id)
    assert failed.status == MeetingStatus.failed
    assert failed.error_code == "RuntimeError"
    assert failed.error_message == "model exploded"
    assert failed.current_stage is None
    assert failed.speakers == [] and failed.segments == []

    with sessions() as session:
        meeting_service.retry_meeting(session, meeting.id)
    assert _drain(sessions, storage, analyzer, tmp_path) == 1

    done = _reload(sessions, meeting.id)
    assert done.status == MeetingStatus.done
    assert done.attempts == 2
    assert done.error_code is None and done.error_message is None
    assert len(done.segments) == 3


def test_missing_recording_fails_the_job(sessions, storage, tmp_path):
    (meeting,) = _queue(sessions, storage, "a.wav")
    storage.objects.clear()
    analyzer = FakeAnalyzer()

    process_next(sessions, storage, analyzer, tmp_path)

    failed = _reload(sessions, meeting.id)
    assert failed.status == MeetingStatus.failed
    assert failed.error_code == "ObjectNotFoundError"
    assert analyzer.calls == []


def test_long_error_message_is_truncated(sessions, storage, tmp_path):
    (meeting,) = _queue(sessions, storage, "a.wav")

    def analyze(audio_path: Path, on_stage) -> MeetingAnalysisResult:
        raise ValueError("x" * 5000)

    process_next(sessions, storage, analyze, tmp_path)
    assert len(_reload(sessions, meeting.id).error_message) == 2000


def test_requeue_interrupted_only_touches_processing(sessions, storage):
    stuck, waiting = _queue(sessions, storage, "stuck.wav", "waiting.wav")
    with sessions() as session:
        assert claim_next(session) == stuck.id

    with sessions() as session:
        assert requeue_interrupted(session) == 1

    requeued = _reload(sessions, stuck.id)
    assert requeued.status == MeetingStatus.queued
    assert requeued.current_stage is None
    assert _reload(sessions, waiting.id).status == MeetingStatus.queued


def test_empty_queue_returns_false(sessions, storage, tmp_path):
    assert process_next(sessions, storage, FakeAnalyzer(), tmp_path) is False


def test_deleting_after_done_removes_only_that_recording(sessions, storage, tmp_path):
    meetings = _queue(sessions, storage, "a.wav", "b.wav")
    _drain(sessions, storage, FakeAnalyzer(), tmp_path)

    with sessions() as session:
        meeting_service.delete_meeting(session, storage, meetings[0].id)

    assert list(storage.objects) == [meetings[1].storage_key]


def test_files_of_one_upload_run_in_upload_order(sessions, storage, tmp_path):
    # One transaction: every row gets the same created_at, so ordering must come from seq.
    names = [f"{i}.wav" for i in range(10)]
    _queue(sessions, storage, *names)
    analyzer = FakeAnalyzer()

    _drain(sessions, storage, analyzer, tmp_path)

    assert [content for _, content in analyzer.calls] == [f"audio:{n}".encode() for n in names]
