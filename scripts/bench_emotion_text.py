"""Compare text emotion models on the UIT-VSMEC test split (693 Vietnamese social media sentences).

    docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.bench_emotion_text MODEL…

Scores are on the six app emotions (`app/services/emotion_labels.py`). The earlier sentiment model, with
only positive / negative / neutral, is mapped positive → happy, negative → angry, neutral → neutral.
The test file is downloaded once to `sample_data/real/vsmec/`.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from app.services.emotion_labels import EMOTIONS, TEXT_LABELS, to_emotions

TEST_URL = "https://huggingface.co/datasets/tridm/UIT-VSMEC/resolve/main/test.json"
TEST_FILE = Path("sample_data/real/vsmec/test.json")
SENTIMENT_LABELS = {"positive": "happy", "negative": "angry", "neutral": "neutral"}


def load_test() -> list[tuple[str, str]]:
    if not TEST_FILE.exists():
        TEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(TEST_URL, TEST_FILE)
    rows = json.loads(TEST_FILE.read_text(encoding="utf-8"))
    return [(row["Sentence"], TEXT_LABELS[row["Emotion"].lower()]) for row in rows]


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    """Mean F1 over the emotions present in the reference (true, predicted pairs)."""
    scores = []
    for emotion in {t for t, _ in pairs}:
        tp = sum(t == p == emotion for t, p in pairs)
        predicted = sum(p == emotion for _, p in pairs)
        actual = sum(t == emotion for t, _ in pairs)
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual
        scores.append(2 * precision * recall / (precision + recall) if tp else 0.0)
    return sum(scores) / len(scores)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="+")
    args = parser.parse_args()

    from transformers import pipeline

    test = load_test()
    print(f"{len(test)} sentences; reference: " + ", ".join(f"{e} {sum(t == e for _, t in test)}" for e in EMOTIONS))
    print("\n| Model | Accuracy | Macro-F1 | Predicted (neutral/happy/sad/angry/surprised/fearful) | ms / sentence (CPU) |")
    print("|---|---|---|---|---|")
    for name in args.models:
        classifier = pipeline("text-classification", model=name, device="cpu", top_k=None)
        labels = {label.lower() for label in classifier.model.config.id2label.values()}
        mapping = SENTIMENT_LABELS if labels <= set(SENTIMENT_LABELS) else TEXT_LABELS
        started = time.perf_counter()
        pairs = []
        for sentence, truth in test:
            result = classifier([sentence], truncation=True, max_length=256)[0]
            scores = {s["label"]: s["score"] for s in result}
            folded = to_emotions(scores, mapping)
            pairs.append((truth, max(folded, key=folded.__getitem__)))
        elapsed = time.perf_counter() - started
        accuracy = sum(t == p for t, p in pairs) / len(pairs)
        predicted = "/".join(str(sum(p == e for _, p in pairs)) for e in EMOTIONS)
        print(f"| {name} | {accuracy:.1%} | {macro_f1(pairs):.1%} | {predicted} | {1000 * elapsed / len(pairs):.0f} |",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
