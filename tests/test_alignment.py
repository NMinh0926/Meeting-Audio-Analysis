"""Tests for alignment service."""
from app.models.schemas import TranscriptSegment, SpeakerSegment
from app.services.alignment import align_segments

def test_align_perfect_overlap():
    transcripts = [
        TranscriptSegment(start=2.0, end=6.0, text="Hello")
    ]
    speakers = [
        SpeakerSegment(speaker="SPEAKER_00", start=1.0, end=3.0), # Overlap: 1.0 (2 to 3)
        SpeakerSegment(speaker="SPEAKER_01", start=3.0, end=8.0)  # Overlap: 3.0 (3 to 6)
    ]
    
    result = align_segments(transcripts, speakers)
    assert len(result) == 1
    assert result[0].speaker == "SPEAKER_01"
    assert result[0].text == "Hello"

def test_align_transcript_inside_speaker():
    transcripts = [
        TranscriptSegment(start=3.0, end=5.0, text="Inside")
    ]
    speakers = [
        SpeakerSegment(speaker="SPEAKER_02", start=2.0, end=6.0)
    ]
    
    result = align_segments(transcripts, speakers)
    assert len(result) == 1
    assert result[0].speaker == "SPEAKER_02"

def test_align_no_strict_overlap_fallback():
    # Transcript completely outside any speaker segment
    transcripts = [
        TranscriptSegment(start=10.0, end=11.0, text="No overlap")
    ]
    speakers = [
        SpeakerSegment(speaker="SPEAKER_00", start=1.0, end=2.0),
        SpeakerSegment(speaker="SPEAKER_01", start=8.0, end=9.0) # Midpoint 8.5 is closer to 10.5 than 1.5
    ]
    
    result = align_segments(transcripts, speakers)
    assert len(result) == 1
    assert result[0].speaker == "SPEAKER_01"

def test_align_empty_inputs():
    assert align_segments([], []) == []
    
    transcripts = [TranscriptSegment(start=1.0, end=2.0, text="a")]
    res = align_segments(transcripts, [])
    assert len(res) == 1
    assert res[0].speaker == "UNKNOWN"


