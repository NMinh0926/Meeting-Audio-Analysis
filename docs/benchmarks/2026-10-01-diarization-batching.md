# Diarization threshold and batched transcription (2026-10-01)

RTX 3050 Ti 4 GB, worker stopped, models as in production (`large-v3-turbo`, pyannote 3.1, ECAPA).

## 1. pyannote clustering threshold
Why: in synthetic meetings, two voices of the same gender are often merged into one speaker.

Ten synthetic meetings of 4 held-out FLEURS voices (3 with 3 men, 2 with 3 women, 5 with 2 + 2; 0.3 s gaps,
each voice speaks once for ~10 s) plus the two 5-minute podcast excerpts (2 speakers each). "Clips sharing
a label" counts voices whose speech went mostly to a speaker label already owning another voice.

| Threshold | Speakers found (truth 4) | Exact count | Clips sharing a label | Podcasts (truth 2) |
|---|---|---|---|---|
| **0.7046 (default)** | 3,3,3,4,4,4,3,3,3,3 | 3/10 | 7/40 | **2, 2** |
| 0.65 | 3,3,3,4,4,4,3,3,3,4 | 4/10 | 6/40 | 2, 2 |
| 0.60 | 3,3,3,4,4,4,3,3,3,4 | 4/10 | 6/40 | 3, 2 |
| 0.55 | 3,3,4,4,4,4,4,3,3,4 | 6/10 | 4/40 | 5, 2 |
| 0.50 | 4,3,4,4,5,4,4,3,4,4 | 7/10 | 2/40 | 3, 1 |

Decision: **keep the default**. Lower thresholds separate the short synthetic voices better but start
splitting real two-person conversations at 0.60; 0.65 differs from the default by one meeting, too small
to trust. The synthetic voices speak once for ~10 s, which is harder than a real meeting where each
person speaks many times. A better lever for later: let users give the number of speakers when they
know it (pyannote accepts `num_speakers` / `min_speakers` / `max_speakers`).

## 2. Batched transcription (`faster_whisper.BatchedInferencePipeline`)
Why: transcription is about half of the processing time of a long file.

Same 10 synthetic meetings as `2026-10-01-decoding.md` (40 clips), plus the user's 3 FLEURS test meetings
(12 clips) in the second table; 32-minute file = Life Abroad ep4; WER on the 120 FLEURS clips.
Batched mode always splits the audio with VAD.

| Mode | 32-min file (s) | GPU peak above idle (MB) | FLEURS WER | Missed clips | Hallucinated |
|---|---|---|---|---|---|
| **sequential (current)** | 111 | 82 | 5.9% | **0/40** | 0 |
| batched, batch 8 | 40 | 146 | 5.9% | 2/40 | 0 |
| batched, batch 16 | 38 | 178 | 5.9% | 2/40 | 0 |

More sensitive VAD settings, batch 8 (missed clips over all 52):

| VAD | 32-min file (s) | FLEURS WER | Missed clips |
|---|---|---|---|
| threshold 0.35, min silence 500 ms, pad 400 ms | 45 | 5.9% | 3/52 |
| threshold 0.25, min silence 500 ms, pad 600 ms | 45 | 5.8% | 3/52 |
| threshold 0.20, min silence 500 ms, pad 800 ms | 45 | 6.0% | 4/52 |

Decision: **keep sequential decoding**. Batching is 2.5–2.8× faster on transcription (≈ 25 % of a long
job) with the same WER, but it drops whole sentences whatever the VAD settings, the same failure that
ruled out the VAD filter. Losing speech is worse than the extra ~70 s per 30 minutes of audio.
