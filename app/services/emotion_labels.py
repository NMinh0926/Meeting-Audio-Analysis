"""The emotions shown to users, how each model's own labels map onto them, and per-speaker summaries."""
from collections.abc import Iterable

# Stored values. "happy", "angry" and "neutral" are also what the earlier sentiment model produced.
EMOTIONS: tuple[str, ...] = ("neutral", "happy", "sad", "angry", "surprised", "fearful")

# UIT-VSMEC labels (Vietnamese text models). Disgust is folded into anger: in a meeting both read as
# irritation, and VSMEC models confuse the two.
TEXT_LABELS: dict[str, str] = {
    "enjoyment": "happy",
    "other": "neutral",
    "sadness": "sad",
    "anger": "angry",
    "disgust": "angry",
    "surprise": "surprised",
    "fear": "fearful",
}

# emotion2vec+ labels, which come as "中文/english"; only the English part is used. Its "disgusted" fired
# on 11/120 calmly read Vietnamese FLEURS clips (none were angry), so it counts as neutral, not anger.
VOICE_LABELS: dict[str, str] = {
    "angry": "angry",
    "disgusted": "neutral",
    "fearful": "fearful",
    "happy": "happy",
    "neutral": "neutral",
    "other": "neutral",
    "sad": "sad",
    "surprised": "surprised",
    "unknown": "neutral",
}


def to_emotions(scores: dict[str, float], mapping: dict[str, str]) -> dict[str, float]:
    """Fold a model's label → probability scores into EMOTIONS (case-insensitive, "中文/english" accepted).

    Labels the mapping does not know are dropped; the result is renormalised to sum to 1.
    """
    folded = dict.fromkeys(EMOTIONS, 0.0)
    for label, score in scores.items():
        emotion = mapping.get(label.split("/")[-1].strip().lower())
        if emotion is not None:
            folded[emotion] += score
    total = sum(folded.values())
    return {e: s / total for e, s in folded.items()} if total > 0 else {**folded, "neutral": 1.0}


EMOTION_NAMES_VI: dict[str, str] = {
    "neutral": "Bình thường",
    "happy": "Vui vẻ",
    "sad": "Buồn",
    "angry": "Tức giận",
    "surprised": "Ngạc nhiên",
    "fearful": "Lo lắng",
}


def emotion_name(emotion: str) -> str:
    return EMOTION_NAMES_VI.get(emotion, EMOTION_NAMES_VI["neutral"])


def speaker_emotions(turns: Iterable[tuple[int, float, str]]) -> dict[int, tuple[str, dict[str, float]]]:
    """Overall emotion of each speaker from (speaker id, turn duration, turn emotion).

    Returns the emotion that fills most of the speaker's talk time, and every emotion's share of it
    (largest first). Ties go to the earlier emotion in EMOTIONS, so to "neutral" first.
    """
    seconds: dict[int, dict[str, float]] = {}
    for speaker, duration, emotion in turns:
        per_emotion = seconds.setdefault(speaker, {})
        per_emotion[emotion] = per_emotion.get(emotion, 0.0) + max(0.0, duration)
    order = {e: i for i, e in enumerate(EMOTIONS)}
    result = {}
    for speaker, per_emotion in seconds.items():
        total = sum(per_emotion.values())
        ranked = sorted(per_emotion, key=lambda e: (-per_emotion[e], order.get(e, len(order))))
        shares = {e: round(per_emotion[e] / total, 4) if total > 0 else 0.0 for e in ranked}
        result[speaker] = (ranked[0], shares)
    return result
