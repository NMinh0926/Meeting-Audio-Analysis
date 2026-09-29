"""Merge consecutive turns by the same speaker."""
from app.core.config import get_settings
from app.models.schemas import SpeakerTurn

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
    current_turn = SpeakerTurn(
        speaker=turns[0].speaker,
        start=turns[0].start,
        end=turns[0].end,
        text=turns[0].text
    )
    
    for next_turn in turns[1:]:
        is_same_speaker = next_turn.speaker == current_turn.speaker
        gap = next_turn.start - current_turn.end
        
        if is_same_speaker and gap <= merge_gap_seconds:
            # Merge into current_turn
            current_turn.end = max(current_turn.end, next_turn.end)
            # Normalize whitespace
            current_turn.text = f"{current_turn.text} {next_turn.text}".strip()
        else:
            merged.append(current_turn)
            current_turn = SpeakerTurn(
                speaker=next_turn.speaker,
                start=next_turn.start,
                end=next_turn.end,
                text=next_turn.text
            )
            
    merged.append(current_turn)
    return merged

