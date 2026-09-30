"""Tests for the WER helpers of scripts/bench_asr.py."""
import pytest

from scripts.bench_asr import normalize, word_errors


def test_normalize_drops_case_and_punctuation():
    assert normalize("Xin chào, mọi người! Hồ sơ du-học.") == ["xin", "chào", "mọi", "người", "hồ", "sơ", "du", "học"]


@pytest.mark.parametrize(
    "reference, hypothesis, errors",
    [
        ("hồ sơ du học", "hồ sơ du học", 0),
        ("hồ sơ du học", "bộ sâu du học", 2),       # two substitutions
        ("cái này rất rẻ", "gái này rẻ", 2),         # one substitution, one deletion
        ("du học", "rưu học ở pháp", 3),             # one substitution, two insertions
        ("", "thêm", 1),
        ("một hai", "", 2),
    ],
)
def test_word_errors(reference, hypothesis, errors):
    assert word_errors(normalize(reference), normalize(hypothesis)) == errors
