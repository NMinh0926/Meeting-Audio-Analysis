# Whisper model comparison for Vietnamese (2026-09-30)

Why: users see many wrong words with Whisper `base` (e.g. "cái" → "gái", "hồ sơ" → "bộ sâu",
"du học" → "rưu học").

## Setup
- 120 FLEURS vi_vn clips (train split, 60 male / 60 female voices, 22.2 min, read speech, CC BY 4.0)
  fetched by `scripts.eval_gender fetch`; reference = FLEURS raw transcription.
- `python -m scripts.bench_asr <models>`: faster-whisper 1.2.1, RTX 3050 Ti 4 GB, `int8_float16`,
  `language="vi"`, default beam size 5. Worker stopped (GPU not shared).
- WER on lowercase words without punctuation (`scripts/bench_asr.py: normalize, word_errors`).
- PhoWhisper (VinAI, BSD-3) converted to CTranslate2 float16 with `--convert`, then run in int8_float16.
- GPU memory = `nvidia-smi` peak minus idle.

## Results

| Model | WER | Errors / words | Time (s) | Time / audio | GPU memory (MB) |
|---|---|---|---|---|---|
| base (current) | 25.9% | 891/3436 | 62 | 0.046 | 259 |
| small | 13.4% | 461/3436 | 80 | 0.060 | 330 |
| medium | 7.9% | 271/3436 | 138 | 0.103 | 970 |
| **large-v3-turbo** | **5.9%** | 202/3436 | 82 | 0.062 | 1066 |
| large-v3-turbo + VAD | 5.9% | 202/3436 | 86 | 0.064 | 1155 |
| vinai/PhoWhisper-small | 12.7% | 435/3436 | 87 | 0.065 | 419 |
| vinai/PhoWhisper-medium | 9.5% | 327/3436 | 154 | 0.116 | 970 |

## Conversational audio (Life Abroad ep4, first 3.5 min, no reference)
Side by side, `base` vs `large-v3-turbo`:
- 5 s: "mẹ mình cũng rất là tìm tình pháp" → "mẹ mình cũng là giáo viên tiếng Pháp"
- 59 s: "được gái là rất tiện" → "được cái là rất tiện"
- 63 s: `base` loops "hồi hồi hồi …" for 10 s → "Campus France là một cái tổ chức hỗ trợ cho sinh viên"
- 88 s: "muốn đi rühr học" → "muốn đi du học ở Pháp"
- 158 s: "học phía rất đề, năm khoảng năm xăm ờ" → "học phí rất rẻ, khoảng 500 euro 1 năm"
- `base` also missed the opening question entirely.

Remaining turbo errors: "hồ sơ" → "bộ sơ" (sometimes), "trường tư" → "trường 4", "DELF" → "Danf",
and one hallucinated outro ("Hãy subscribe cho kênh …") at the cut end of the excerpt — the VAD filter
is meant to suppress this kind of output on silence.

## Conclusion
`large-v3-turbo` cuts word errors from 25.9 % to 5.9 % (4.4× fewer) at about the speed of `small` and
~1.1 GB of GPU memory. PhoWhisper does worse than turbo on this set.
