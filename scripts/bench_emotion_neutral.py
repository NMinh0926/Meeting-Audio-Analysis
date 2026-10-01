"""How often calm read speech gets an emotion: voice, text and combined, on the 120 FLEURS clips.

    docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.bench_emotion_neutral

FLEURS speakers read Wikipedia sentences in a flat voice, so "neutral" is the expected answer for nearly
every clip; anything else is a false emotion. This checks the voice model on Vietnamese, for which no
labelled emotional speech is available. Clips come from `scripts.eval_gender fetch`. Stop the worker first.
"""
import collections
import sys
import time

from faster_whisper import decode_audio

from app.core.config import get_settings
from app.services.emotion import combine, text_scores, voice_scores
from app.services.emotion_labels import EMOTIONS
from scripts.eval_gender import load_manifest


def main() -> int:
    settings = get_settings()
    margin = settings.EMOTION_MIN_MARGIN
    clips = load_manifest()
    counts: dict[str, collections.Counter] = {side: collections.Counter() for side in ("voice", "text", "combined")}
    started = time.perf_counter()
    for clip in clips:
        samples = decode_audio(str(clip.path), sampling_rate=16000)
        voice = voice_scores(samples, settings.EMOTION_CHUNK_SECONDS, settings.EMOTION_MIN_SECONDS)
        text = text_scores([(clip.text, len(samples) / 16000)])
        counts["voice"][combine(voice, None, 1.0, margin).sentiment] += 1
        counts["text"][combine(None, text, 0.0, margin).sentiment] += 1
        counts["combined"][combine(voice, text, settings.EMOTION_VOICE_WEIGHT, margin).sentiment] += 1
    elapsed = time.perf_counter() - started

    print(f"{len(clips)} clips, {elapsed:.0f} s, voice weight {settings.EMOTION_VOICE_WEIGHT}, min margin {margin}\n")
    print(f"| Side | Neutral | False emotion | {' | '.join(EMOTIONS[1:])} |")
    print("|---|---|---|" + "---|" * (len(EMOTIONS) - 1))
    for side, counter in counts.items():
        other = len(clips) - counter["neutral"]
        print(f"| {side} | {counter['neutral']}/{len(clips)} | {other / len(clips):.1%} | "
              + " | ".join(str(counter[e]) for e in EMOTIONS[1:]) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
