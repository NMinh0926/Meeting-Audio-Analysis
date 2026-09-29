"""Align transcript segments with speaker segments."""
from app.models.schemas import TranscriptSegment, SpeakerSegment, SpeakerTurn

def align_segments(
    transcripts: list[TranscriptSegment], 
    speakers: list[SpeakerSegment]
) -> list[SpeakerTurn]:
    """Aligns transcripts with speakers using maximum time overlap.
    
    If there is no strict overlap, uses a fallback based on the nearest temporal midpoint.
    """
    if not transcripts:
        return []
        
    if not speakers:
        # Fallback if no speakers were detected but we have transcript
        return [SpeakerTurn(speaker="UNKNOWN", start=t.start, end=t.end, text=t.text) for t in transcripts]

    result = []
    
    for t in transcripts:
        best_speaker = None
        max_overlap = -1.0
        
        for s in speakers:
            # Calculate time overlap
            overlap = max(0.0, min(t.end, s.end) - max(t.start, s.start))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = s.speaker
                
        # Fallback: if no strict overlap (>0), find nearest speaker by midpoint
        if max_overlap <= 0.0 or best_speaker is None:
            t_mid = (t.start + t.end) / 2.0
            min_dist = float('inf')
            
            for s in speakers:
                s_mid = (s.start + s.end) / 2.0
                dist = abs(t_mid - s_mid)
                if dist < min_dist:
                    min_dist = dist
                    best_speaker = s.speaker
                    
        if best_speaker is None:
            best_speaker = "UNKNOWN" # Absolute fallback, should not happen if speakers exist
            
        result.append(SpeakerTurn(
            speaker=best_speaker,
            start=t.start,
            end=t.end,
            text=t.text
        ))
        
    return result

