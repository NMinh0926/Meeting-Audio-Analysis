"""Tests for segment merger service."""
from app.models.schemas import SpeakerTurn
from app.services.segment_merger import merge_consecutive_turns


def _turn(speaker, start, end, text):
    return SpeakerTurn(speaker=speaker, start=start, end=end, text=text)


def test_merge_same_speaker_within_gap():
    turns = [
        _turn("SPEAKER_00", 0.0, 2.0, "Xin chào"),
        _turn("SPEAKER_00", 2.5, 4.0, "mọi người."),
    ]

    result = merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert len(result) == 1
    assert result[0].start == 0.0
    assert result[0].end == 4.0
    assert result[0].text == "Xin chào mọi người."


def test_no_merge_when_gap_too_large():
    turns = [
        _turn("SPEAKER_00", 0.0, 2.0, "Một"),
        _turn("SPEAKER_00", 5.0, 6.0, "Hai"),
    ]

    result = merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert [t.text for t in result] == ["Một", "Hai"]


def test_no_merge_across_speakers():
    turns = [
        _turn("SPEAKER_00", 0.0, 2.0, "Câu hỏi?"),
        _turn("SPEAKER_01", 2.1, 3.0, "Trả lời."),
        _turn("SPEAKER_00", 3.1, 4.0, "Cảm ơn."),
    ]

    result = merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert [t.speaker for t in result] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_overlapping_turns_keep_latest_end():
    turns = [
        _turn("SPEAKER_00", 0.0, 5.0, "Dài"),
        _turn("SPEAKER_00", 1.0, 3.0, "ngắn"),
    ]

    result = merge_consecutive_turns(turns, merge_gap_seconds=0.0)

    assert len(result) == 1
    assert result[0].end == 5.0


def test_does_not_mutate_input():
    turns = [
        _turn("SPEAKER_00", 0.0, 1.0, "A"),
        _turn("SPEAKER_00", 1.0, 2.0, "B"),
    ]

    merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert turns[0].end == 1.0
    assert turns[0].text == "A"


def test_empty_input():
    assert merge_consecutive_turns([]) == []


def test_default_gap_from_settings(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setattr(
        "app.services.segment_merger.get_settings",
        lambda: Settings(MERGE_GAP_SECONDS=0.5),
    )
    turns = [
        _turn("SPEAKER_00", 0.0, 1.0, "A"),
        _turn("SPEAKER_00", 2.0, 3.0, "B"),
    ]

    assert len(merge_consecutive_turns(turns)) == 2


def test_merged_turn_keeps_each_part_as_utterance():
    turns = [
        _turn("SPEAKER_00", 0.0, 2.0, "Xin chào"),
        _turn("SPEAKER_00", 2.5, 4.0, "mọi người."),
        _turn("SPEAKER_01", 4.2, 5.0, "Chào anh."),
    ]

    result = merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert [(u.start, u.end, u.text) for u in result[0].utterances] == [
        (0.0, 2.0, "Xin chào"), (2.5, 4.0, "mọi người.")]
    assert [(u.start, u.end, u.text) for u in result[1].utterances] == [(4.2, 5.0, "Chào anh.")]


def test_merge_does_not_share_utterance_lists_with_input():
    turns = [_turn("SPEAKER_00", 0.0, 1.0, "Một"), _turn("SPEAKER_00", 1.5, 2.0, "Hai")]

    merge_consecutive_turns(turns, merge_gap_seconds=1.0)

    assert all(t.utterances == [] for t in turns)
