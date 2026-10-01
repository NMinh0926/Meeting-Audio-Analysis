"""Tests for the span arithmetic of scripts.bench_transcript (no model involved)."""
import pytest

from scripts.bench_transcript import merge, uncovered


def test_merge_joins_overlapping_and_touching_spans():
    assert merge([(5.0, 6.0), (0.0, 2.0), (1.5, 3.0), (3.0, 4.0)]) == [(0.0, 4.0), (5.0, 6.0)]


def test_merge_of_nothing_is_empty():
    assert merge([]) == []


@pytest.mark.parametrize(("speech", "covered", "expected"), [
    ([(0.0, 10.0)], [], [(0.0, 10.0)]),
    ([(0.0, 10.0)], [(0.0, 10.0)], []),
    ([(0.0, 10.0)], [(2.0, 4.0), (6.0, 7.0)], [(0.0, 2.0), (4.0, 6.0), (7.0, 10.0)]),
    ([(0.0, 3.0), (5.0, 8.0)], [(2.0, 6.0)], [(0.0, 2.0), (6.0, 8.0)]),
    ([(5.0, 6.0)], [(0.0, 1.0), (9.0, 10.0)], [(5.0, 6.0)]),
    ([(1.0, 2.0), (3.0, 4.0)], [(0.0, 5.0)], []),
])
def test_uncovered_is_speech_without_words(speech, covered, expected):
    assert uncovered(speech, covered) == expected
