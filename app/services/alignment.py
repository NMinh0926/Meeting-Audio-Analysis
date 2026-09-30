"""Align transcript segments with speaker segments."""
from app.models.schemas import TranscriptSegment, SpeakerSegment, SpeakerTurn, Word

# A single word this short, surrounded by another speaker, is treated as diarization jitter.
MAX_ISOLATED_WORD_SECONDS = 0.5


def _speaker_at(start: float, end: float, speakers: list[SpeakerSegment]) -> str:
    """Speaker overlapping [start, end] the most, or the nearest one by midpoint if none overlaps."""
    best_speaker = None
    max_overlap = 0.0
    for s in speakers:
        overlap = min(end, s.end) - max(start, s.start)
        if overlap > max_overlap:
            max_overlap = overlap
            best_speaker = s.speaker
    if best_speaker is not None:
        return best_speaker

    midpoint = (start + end) / 2.0
    return min(speakers, key=lambda s: abs(midpoint - (s.start + s.end) / 2.0)).speaker


def _smooth(labels: list[str], words: list[Word]) -> list[str]:
    """Relabel a lone short word whose neighbours on both sides belong to the same other speaker."""
    smoothed = list(labels)
    for i in range(1, len(labels) - 1):
        neighbour = labels[i - 1]
        is_lone = labels[i] != neighbour and labels[i + 1] == neighbour
        if is_lone and words[i].end - words[i].start <= MAX_ISOLATED_WORD_SECONDS:
            smoothed[i] = neighbour
    return smoothed


def _split_by_speaker(segment: TranscriptSegment, speakers: list[SpeakerSegment]) -> list[SpeakerTurn]:
    """Give each word its speaker and cut the sentence wherever the speaker changes."""
    labels = _smooth([_speaker_at(w.start, w.end, speakers) for w in segment.words], segment.words)
    turns: list[SpeakerTurn] = []
    run: list[Word] = []

    def flush() -> None:
        text = "".join(w.text for w in run).strip()
        if text:
            turns.append(SpeakerTurn(speaker=run_speaker, start=run[0].start, end=run[-1].end, text=text))

    run_speaker = labels[0]
    for word, label in zip(segment.words, labels):
        if label != run_speaker:
            flush()
            run, run_speaker = [], label
        run.append(word)
    flush()
    return turns


def align_segments(
    transcripts: list[TranscriptSegment],
    speakers: list[SpeakerSegment]
) -> list[SpeakerTurn]:
    """Aligns transcripts with speakers using maximum time overlap.

    With word timings, each word is assigned on its own and a sentence spoken by two people is split
    at the change. Without them the whole segment goes to one speaker. If there is no strict overlap,
    the speaker with the nearest temporal midpoint is used.
    """
    if not transcripts:
        return []

    if not speakers:
        # Fallback if no speakers were detected but we have transcript
        return [SpeakerTurn(speaker="UNKNOWN", start=t.start, end=t.end, text=t.text) for t in transcripts]

    result = []
    for t in transcripts:
        if t.words:
            result.extend(_split_by_speaker(t, speakers))
        else:
            result.append(SpeakerTurn(speaker=_speaker_at(t.start, t.end, speakers), start=t.start, end=t.end,
                                      text=t.text))
    return result
