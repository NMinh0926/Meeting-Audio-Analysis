"""Merge consecutive turns by the same speaker."""
from app.core.config import get_settings
from app.models.schemas import SpeakerTurn, TranscriptSegment


def _utterance(turn: SpeakerTurn) -> TranscriptSegment:
    return TranscriptSegment(start=turn.start, end=turn.end, text=turn.text)


def _start_turn(turn: SpeakerTurn) -> SpeakerTurn:
    """A new merged turn holding one unmerged turn as its first utterance."""
    return SpeakerTurn(
        speaker=turn.speaker,
        start=turn.start,
        end=turn.end,
        text=turn.text,
        utterances=[_utterance(turn)],
    )


def merge_consecutive_turns(
    turns: list[SpeakerTurn],
    merge_gap_seconds: float | None = None
) -> list[SpeakerTurn]:
    """Merges consecutive turns from the same speaker if the gap is within the limit."""
    if not turns:
        return []
        
    if merge_gap_seconds is None:
        merge_gap_seconds = get_settings().MERGE_GAP_SECONDS
        
    merged = []
    
    # We create copies to avoid mutating the original input objects
    current_turn = _start_turn(turns[0])
    
    for next_turn in turns[1:]:
        is_same_speaker = next_turn.speaker == current_turn.speaker
        gap = next_turn.start - current_turn.end
        
        if is_same_speaker and gap <= merge_gap_seconds:
            # Merge into current_turn
            current_turn.end = max(current_turn.end, next_turn.end)
            # Normalize whitespace
            current_turn.text = f"{current_turn.text} {next_turn.text}".strip()
            current_turn.utterances.append(_utterance(next_turn))
        else:
            merged.append(current_turn)
            current_turn = _start_turn(next_turn)
            
    merged.append(current_turn)
    return merged

