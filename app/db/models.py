"""PostgreSQL schema. Original recordings live in S3 under Meeting.storage_key."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Identity, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MeetingStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Upload order. created_at is the transaction time, shared by every file of one upload.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, name="meeting_status", values_callable=lambda members: [m.value for m in members]),
        default=MeetingStatus.queued,
    )
    # Pipeline stage the worker is running; None when not processing.
    current_stage: Mapped[str | None] = mapped_column(String(50))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    duration_seconds: Mapped[float | None] = mapped_column(Float)
    speaker_count: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    speakers: Mapped[list["Speaker"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="Speaker.label"
    )
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="Segment.start"
    )

    # The worker claims the oldest queued meeting first.
    __table_args__ = (Index("ix_meetings_status_seq", "status", "seq"),)


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    # Label from diarization, e.g. SPEAKER_00; display_name is what users rename.
    label: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str] = mapped_column(String(20))
    gender_confidence: Mapped[float] = mapped_column(Float)

    meeting: Mapped[Meeting] = relationship(back_populates="speakers")


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    speaker_id: Mapped[int] = mapped_column(ForeignKey("speakers.id", ondelete="CASCADE"), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(20))
    sentiment_confidence: Mapped[float] = mapped_column(Float)

    meeting: Mapped[Meeting] = relationship(back_populates="segments")
    speaker: Mapped[Speaker] = relationship()
    utterances: Mapped[list["Utterance"]] = relationship(
        back_populates="segment", cascade="all, delete-orphan", passive_deletes=True, order_by="Utterance.start"
    )


class Utterance(Base):
    """One transcript sentence (a Whisper segment) inside a merged turn: the unit for subtitles and seeking."""

    __tablename__ = "utterances"

    id: Mapped[int] = mapped_column(primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id", ondelete="CASCADE"), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    segment: Mapped[Segment] = relationship(back_populates="utterances")
