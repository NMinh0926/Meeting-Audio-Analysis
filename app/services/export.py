"""Transcript exports. Speaker names are the current display names."""
import enum
import math
from collections.abc import Callable
from pathlib import Path

from app.db.models import Meeting


class ExportFormat(str, enum.Enum):
    txt = "txt"
    srt = "srt"


def format_clock(seconds: float) -> str:
    """HH:MM:SS, rounded down to the second."""
    total = max(0, math.floor(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm as SubRip expects."""
    millis = max(0, round(seconds * 1000))
    return f"{format_clock(millis // 1000)},{millis % 1000:03d}"


def to_txt(meeting: Meeting) -> str:
    """Readable transcript: a header, then one paragraph per speaker turn."""
    lines = [
        meeting.filename,
        f"Thời lượng: {format_clock(meeting.duration_seconds or 0)}",
        f"Người nói: {', '.join(speaker.display_name for speaker in meeting.speakers)}",
        "",
    ]
    for turn in meeting.segments:
        lines.append(
            f"[{format_clock(turn.start)} - {format_clock(turn.end)}] {turn.speaker.display_name}: {turn.text}"
        )
        lines.append("")
    return "\n".join(lines)


def to_srt(meeting: Meeting) -> str:
    """Subtitles: one cue per utterance, prefixed with the speaker name."""
    cues = []
    utterances = [(turn.speaker.display_name, u) for turn in meeting.segments for u in turn.utterances]
    for index, (speaker, utterance) in enumerate(utterances, start=1):
        cues.append(
            f"{index}\n"
            f"{format_srt_time(utterance.start)} --> {format_srt_time(utterance.end)}\n"
            f"{speaker}: {utterance.text}\n"
        )
    return "\n".join(cues)


_EXPORTERS: dict[ExportFormat, tuple[Callable[[Meeting], str], str]] = {
    ExportFormat.txt: (to_txt, "text/plain; charset=utf-8"),
    ExportFormat.srt: (to_srt, "application/x-subrip; charset=utf-8"),
}


def export_transcript(meeting: Meeting, export_format: ExportFormat) -> tuple[str, str, str]:
    """Return (content, media type, download filename) for a processed meeting."""
    render, media_type = _EXPORTERS[export_format]
    return render(meeting), media_type, f"{Path(meeting.filename).stem}.{export_format.value}"
