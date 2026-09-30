"""Transcript exports. Speaker names are the current display names, each tagged with the detected gender."""
import enum
import json
import math
from collections.abc import Callable
from pathlib import Path

from app.db.models import Meeting, Speaker


class ExportFormat(str, enum.Enum):
    txt = "txt"
    srt = "srt"
    json = "json"


GENDER_LABELS: dict[str, str] = {"male": "Nam", "female": "Nữ"}
UNKNOWN_GENDER_LABEL = "Không rõ"


def format_clock(seconds: float) -> str:
    """HH:MM:SS, rounded down to the second."""
    total = max(0, math.floor(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm as SubRip expects."""
    millis = max(0, round(seconds * 1000))
    return f"{format_clock(millis // 1000)},{millis % 1000:03d}"


def gender_label(gender: str) -> str:
    return GENDER_LABELS.get(gender, UNKNOWN_GENDER_LABEL)


def speaker_tag(speaker: Speaker) -> str:
    """Name with gender, e.g. "Chị Lan (Nữ)"."""
    return f"{speaker.display_name} ({gender_label(speaker.gender)})"


def _speaker_summary(speaker: Speaker) -> str:
    """Name with gender and confidence for the TXT header, e.g. "Chị Lan (Nữ, 98%)"."""
    if speaker.gender not in GENDER_LABELS:
        return speaker_tag(speaker)
    return f"{speaker.display_name} ({gender_label(speaker.gender)}, {round(speaker.gender_confidence * 100)}%)"


def to_txt(meeting: Meeting) -> str:
    """Readable transcript: a header, then one paragraph per speaker turn."""
    lines = [
        meeting.filename,
        f"Thời lượng: {format_clock(meeting.duration_seconds or 0)}",
        f"Người nói: {', '.join(_speaker_summary(speaker) for speaker in meeting.speakers)}",
        "",
    ]
    for turn in meeting.segments:
        lines.append(f"[{format_clock(turn.start)} - {format_clock(turn.end)}] {speaker_tag(turn.speaker)}: {turn.text}")
        lines.append("")
    return "\n".join(lines)


def to_srt(meeting: Meeting) -> str:
    """Subtitles: one cue per utterance, prefixed with the speaker name and gender."""
    cues = []
    utterances = [(speaker_tag(turn.speaker), u) for turn in meeting.segments for u in turn.utterances]
    for index, (speaker, utterance) in enumerate(utterances, start=1):
        cues.append(
            f"{index}\n"
            f"{format_srt_time(utterance.start)} --> {format_srt_time(utterance.end)}\n"
            f"{speaker}: {utterance.text}\n"
        )
    return "\n".join(cues)


def to_json(meeting: Meeting) -> str:
    """Everything extracted from the recording, for other systems."""
    data = {
        "meeting_id": str(meeting.id),
        "filename": meeting.filename,
        "duration_seconds": meeting.duration_seconds,
        "speakers": [
            {"id": s.id, "label": s.label, "name": s.display_name,
             "gender": s.gender, "gender_confidence": s.gender_confidence}
            for s in meeting.speakers
        ],
        "turns": [
            {"speaker_id": t.speaker_id, "speaker": t.speaker.display_name, "gender": t.speaker.gender,
             "start": t.start, "end": t.end, "text": t.text,
             "sentiment": t.sentiment, "sentiment_confidence": t.sentiment_confidence,
             "utterances": [{"start": u.start, "end": u.end, "text": u.text} for u in t.utterances]}
            for t in meeting.segments
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


_EXPORTERS: dict[ExportFormat, tuple[Callable[[Meeting], str], str]] = {
    ExportFormat.txt: (to_txt, "text/plain; charset=utf-8"),
    ExportFormat.srt: (to_srt, "application/x-subrip; charset=utf-8"),
    ExportFormat.json: (to_json, "application/json"),
}


def export_transcript(meeting: Meeting, export_format: ExportFormat) -> tuple[str, str, str]:
    """Return (content, media type, download filename) for a processed meeting."""
    render, media_type = _EXPORTERS[export_format]
    return render(meeting), media_type, f"{Path(meeting.filename).stem}.{export_format.value}"
