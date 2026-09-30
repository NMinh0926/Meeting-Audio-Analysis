# Baseline: full pipeline through the worker (2026-09-30)

First end-to-end run with real models, before any performance work (Phase 6 compares against this).

## Setup
- GPU: RTX 3050 Ti Laptop, 4 GB, `DEVICE=cuda`, `COMPUTE_TYPE=int8_float16`; Docker Desktop on Windows 11.
- Models: Whisper `base`, `pyannote/speaker-diarization-3.1` (pyannote.audio 4.0.7),
  gender `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech`,
  sentiment `lxyuan/distilbert-base-multilingual-cased-sentiments-student`.
- One worker, one job at a time; models stay loaded between jobs.
- Five files uploaded in one `POST /api/v1/meetings`, processed in upload order.
- Audio: `sample_data/sample_meeting.wav` (synthetic TTS, 3 voices) and Life Abroad Podcast
  episodes 4 and 8 (archive.org, CC BY-NC-ND 3.0; 2-person interviews), full and 5-minute clips
  (`sample_data/real/`, not committed).
- Stage times come from worker log timestamps (time from one stage start to the next).

## Results (seconds)

| File | Audio | Download | Preprocess | Whisper | Diarization | Gender | Sentiment | Total | Total / audio | Speakers found |
|---|---|---|---|---|---|---|---|---|---|---|
| sample_meeting.wav ¹ | 53 | 0.2 | 0.1 | 5.5 | 38.8 | 48.7 | 18.7 | 112.0 | 2.10 | 5 (truth: 3) |
| ep4 clip (5 min) | 300 | 0.9 | 8.7 | 31.7 | 201.1 | 31.4 | 2.6 | 276.7 | 0.92 | 2 |
| ep8 clip (5 min) | 300 | 0.5 | 8.3 | 115.3 | 420.1 | 81.0 | 0.9 | 626.9 | 2.09 | 2 |
| ep4 (32 min) | 1922 | 1.4 | 28.0 | 160.1 | 1030.9 | 28.1 | 1.8 | 1250.6 | 0.65 | 3 (expected 2) |
| ep8 (45 min) | 2676 | 0.6 | 17.6 | 325.2 | 1305.4 | 609.6 | 3.1 | 2262.1 | 0.85 | 2 |
| **All 5** | **5251** | | | | | | | **4528.3** | **0.86** | |

¹ First job: includes loading the diarization, gender and sentiment models (pyannote files were
already cached by an earlier `scripts.run_pipeline` run).

Alignment and merging take under 1 s in every job and are left out.

## Observations
- **Diarization dominates**: 58–82 % of each job after the first (35 % there, where model loading
  weighs more); about 0.5 × audio length on the long episodes.
- **GPU memory is full**: `nvidia-smi` peaked at 3932 MB of 4096 MB while the worker ran
  (host total, includes the desktop). The same stage varies a lot between similar inputs
  (Whisper 31.7 s vs 115.3 s on two 5-minute clips; gender 28 s on 32 min vs 610 s on 45 min),
  which points to memory pressure (spill to shared system memory) rather than input length.
- pyannote logs `CUDACachingAllocator ... OOM ... 9267314688 bytes` once or twice per job. It comes
  from `min_num_samples` in `pyannote/audio/pipelines/speaker_verification.py`, which probes input
  sizes and catches the `RuntimeError` on purpose; results are not affected.
- Earlier standalone run (`scripts.run_pipeline`, fresh process, ep4 clip): Whisper 18.6 s,
  diarization 110 s (including the first download of the pyannote models).

## Ideas for Phase 6
- Release models between stages or run gender/sentiment on CPU so diarization has the GPU to itself.
- Tune pyannote `embedding_batch_size` / `segmentation_batch_size` (config default 32).
- Larger Whisper model once memory is under control (`base` makes many Vietnamese errors).
