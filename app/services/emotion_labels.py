"""The emotions shown to users, and how each model's own labels map onto them."""

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

# emotion2vec+ labels, which come as "中文/english"; only the English part is used.
VOICE_LABELS: dict[str, str] = {
    "angry": "angry",
    "disgusted": "angry",
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
