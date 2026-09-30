"""Tests for alignment service."""
from app.models.schemas import TranscriptSegment, SpeakerSegment, Word
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




def _words(*items):
    """(start, end, text) → Word list; text carries Whisper's leading space."""
    return [Word(start=s, end=e, text=f" {t}") for s, e, t in items]


def test_sentence_spoken_by_two_people_is_split_at_the_change():
    speakers = [SpeakerSegment(speaker="A", start=0.0, end=2.0), SpeakerSegment(speaker="B", start=2.1, end=5.0)]
    words = _words((0.0, 0.5, "thì"), (0.5, 1.0, "khoảng"), (1.0, 1.9, "ba nghìn."),
                   (2.2, 2.6, "Ba"), (2.6, 3.0, "nghìn"), (3.0, 3.6, "một"), (3.6, 4.0, "năm?"))
    segment = TranscriptSegment(start=0.0, end=4.0, text="thì khoảng ba nghìn. Ba nghìn một năm?", words=words)

    turns = align_segments([segment], speakers)

    assert [(t.speaker, t.start, t.end, t.text) for t in turns] == [
        ("A", 0.0, 1.9, "thì khoảng ba nghìn."),
        ("B", 2.2, 4.0, "Ba nghìn một năm?"),
    ]


def test_lone_short_word_of_another_speaker_is_smoothed():
    speakers = [SpeakerSegment(speaker="A", start=0.0, end=1.0), SpeakerSegment(speaker="B", start=1.0, end=1.3),
                SpeakerSegment(speaker="A", start=1.3, end=3.0)]
    words = _words((0.0, 1.0, "học"), (1.0, 1.3, "phí"), (1.3, 3.0, "rất rẻ"))
    segment = TranscriptSegment(start=0.0, end=3.0, text="học phí rất rẻ", words=words)

    turns = align_segments([segment], speakers)

    assert [(t.speaker, t.text) for t in turns] == [("A", "học phí rất rẻ")]


def test_long_word_of_another_speaker_is_kept():
    speakers = [SpeakerSegment(speaker="A", start=0.0, end=1.0), SpeakerSegment(speaker="B", start=1.0, end=2.0),
                SpeakerSegment(speaker="A", start=2.0, end=3.0)]
    words = _words((0.0, 1.0, "Vâng"), (1.0, 2.0, "Dạ"), (2.0, 3.0, "đúng"))
    segment = TranscriptSegment(start=0.0, end=3.0, text="Vâng Dạ đúng", words=words)

    assert [(t.speaker, t.text) for t in align_segments([segment], speakers)] == [
        ("A", "Vâng"), ("B", "Dạ"), ("A", "đúng")]


def test_segment_without_words_goes_to_one_speaker():
    speakers = [SpeakerSegment(speaker="A", start=0.0, end=1.0), SpeakerSegment(speaker="B", start=1.0, end=4.0)]
    segment = TranscriptSegment(start=0.5, end=3.0, text="không có mốc từ")

    assert [(t.speaker, t.text) for t in align_segments([segment], speakers)] == [("B", "không có mốc từ")]
