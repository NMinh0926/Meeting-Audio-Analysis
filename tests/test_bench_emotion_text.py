"""Tests for the scoring of scripts.bench_emotion_text (no model involved)."""
import pytest

from scripts.bench_emotion_text import macro_f1


def test_macro_f1_is_one_when_every_prediction_is_right():
    assert macro_f1([("happy", "happy"), ("sad", "sad")]) == 1.0


def test_macro_f1_averages_per_emotion_f1():
    # happy: precision 1/2, recall 1 → 2/3; sad: never predicted → 0
    assert macro_f1([("happy", "happy"), ("sad", "happy")]) == pytest.approx(1 / 3)


def test_macro_f1_ignores_emotions_absent_from_the_reference():
    assert macro_f1([("happy", "happy"), ("happy", "angry")]) == pytest.approx(2 / 3)
