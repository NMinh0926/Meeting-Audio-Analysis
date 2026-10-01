# Missed and wrong words in conversation: decoding options, large-v3, hotwords (2026-10-01)

Why: the user sees dropped words and a few wrong ones in the podcasts, e.g. at the start of
`life_abroad_ep8.mp3`: "Nguyễn Đăng Chí" → "Nguyễn Đăng", "khách mời" → "khách mở".

## Setup
- RTX 3050 Ti 4 GB, worker stopped, `int8_float16`, `language="vi"`, `word_timestamps=True`,
  `condition_on_previous_text=False` in every run.
- `python -m scripts.bench_transcript FILE… --model M --variants … --fleurs`. Without a reference text,
  **missed speech** = seconds pyannote marks as speech with no transcribed word within 0.3 s.
  Gaps ≥ 2 s are listed for review. FLEURS WER on the 120 clips of `2026-09-30-asr-models.md`.
- Files: Life Abroad ep8 (44.6 min, 2509 s of speech) and ep4 (32 min, 1664 s), whole files after the
  pipeline's normalization, as in production.

## Results

| Model | Decoding | Missed ep8 | Missed ep4 | Gaps ≥ 2 s (ep8 + ep4) | FLEURS WER | Time ep8 / ep4 (s) |
|---|---|---|---|---|---|---|
| **large-v3-turbo** | **current** (hallucination silence 2 s) | **30.9 s (1.2 %)** | **89.3 s (5.4 %)** | 2 + 4 | 5.9 % | **140 / 89** |
| large-v3-turbo | hallucination silence 4 s | 30.9 s (1.2 %) | 89.3 s (5.4 %) | 2 + 4 | 5.9 % | 131 / 84 |
| large-v3-turbo | + Vietnamese `initial_prompt` | 29.7 s (1.2 %) | 89.3 s (5.4 %) | 2 + 4 | 6.0 % | 129 / 85 |
| large-v3 | current | 58.8 s (2.3 %) | 110.4 s (6.6 %) | 4 + 6 | 5.6 % | 409 / 248 |

What the gaps ≥ 2 s are (turbo, current): the spoken introduction over the theme music at ~10–17 s in
both episodes, and four short lines at speaker changes (2–3 s each). The rest of the missed time is
spread in pieces under 2 s (fillers, overlaps, word-timestamp slack).

## The opening of ep8 is unstable, not cut by a bug
The first 50 s decoded from the raw MP3 and from the normalized WAV (same length and peak, 16-bit PCM)
differ: raw keeps "Khách mời của chương trình hôm nay là bạn Chí…", normalized drops it to
"…và du học sinh…", and "Chí"/"Trí", "khách mời"/"khách mở" flip between the two and between a 120 s and a
600 s excerpt. `large-v3` is steadier on the opening line but still writes "khách mở" and "Trí".
These words sit at the edge of what the model hears (speech over music, a name), so tiny input changes
flip them; no decoding option above fixes that.

## Hotwords (faster-whisper `hotwords`)
ep8 opening, turbo, normalized WAV, two excerpt lengths:

| Hotwords | Guest's name | "khách mời" | Opening line |
|---|---|---|---|
| none | "Trí" in both | right in 1/2 | cut in both |
| `Nguyễn Đăng Chí, khách mời` | **"Nguyễn Đăng Chí" in both** | **right in 2/2** | full in 1/2 |
| `Chí, khách mời, Life Abroad` | "Trí" in both | right in 2/2 | cut in both |

Side effects on FLEURS (texts that never contain these words), hotwords `Nguyễn Đăng Chí, khách mời`:
WER 5.9 % → 6.1 % (202 → 210 errors of 3436), 0/120 clips with a hotword inserted.

## Decision
- Keep `large-v3-turbo` with the current decoding: the alternatives miss as much or more speech, and
  `large-v3` is 3× slower for a 0.3-point WER gain.
- Hotwords fix names and terms the user knows in advance when the full form is given (a partial name
  does not help). Worth offering as an optional per-meeting field; not applied by default.
