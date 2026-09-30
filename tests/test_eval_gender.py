"""Tests for the pure helpers of scripts/eval_gender.py (no network, no models)."""
from scripts.eval_gender import (accuracy_table, attribution_accuracy, mixed_utterances, select_balanced,
                                 speaker_for_span)


def test_select_balanced_caps_each_gender_and_skips_duplicates():
    rows = [(f"m{i}.wav", "câu", "MALE") for i in range(5)] + [(f"f{i}.wav", "câu", "FEMALE") for i in range(2)]
    rows += [("m0.wav", "câu", "MALE"), ("x.wav", "câu", "OTHER")]

    chosen = select_balanced(rows, per_gender=3)

    assert sum(g == "male" for g, _ in chosen.values()) == 3
    assert sum(g == "female" for g, _ in chosen.values()) == 2
    assert "x.wav" not in chosen
    assert select_balanced(rows, per_gender=3) == chosen  # seeded


def test_speaker_for_span_picks_largest_overlap():
    turns = [(0.0, 2.0, "A"), (2.0, 5.0, "B"), (5.0, 6.0, "A")]
    assert speaker_for_span(turns, 1.5, 4.0) == "B"
    assert speaker_for_span(turns, 0.0, 1.9) == "A"
    assert speaker_for_span(turns, 10.0, 12.0) is None


def test_accuracy_table_counts_and_thresholds():
    results = [("male", "male", 0.95), ("male", "female", 0.55), ("female", "female", 0.85),
               ("female", "unknown", 0.0)]

    table = accuracy_table(results)

    assert "| male | 2 | 1 | 1 | 0 |" in table
    assert "| female | 2 | 1 | 0 | 1 |" in table
    assert "| 0.00 | 3/4 | 66.7% |" in table
    assert "| 0.60 | 2/4 | 100.0% |" in table
    assert "| 0.80 | 2/4 | 100.0% |" in table


SPANS = [(0.0, 5.0, "male"), (5.2, 10.0, "female")]


def test_mixed_utterances_counts_sentences_spanning_two_speakers():
    utterances = [(0.0, 3.0, "A"), (3.0, 6.0, "A"), (6.0, 10.0, "B"), (4.9, 5.3, "B")]
    # (3, 6) holds 2 s of the first clip and 0.8 s of the second; (4.9, 5.3) only brushes both.
    assert mixed_utterances(utterances, SPANS) == 1


def test_attribution_accuracy_weights_by_time():
    assert attribution_accuracy([(0.0, 5.0, "A"), (5.2, 10.0, "B")], SPANS) == 1.0
    # The second clip's first 0.8 s is labelled A, the first clip's owner.
    utterances = [(0.0, 6.0, "A"), (6.0, 10.0, "B")]
    assert attribution_accuracy(utterances, SPANS) == (5.0 + 4.0) / (5.0 + 0.8 + 4.0)
    assert attribution_accuracy([], SPANS) == 0.0
