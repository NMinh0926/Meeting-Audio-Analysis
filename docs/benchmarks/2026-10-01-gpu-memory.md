# GPU memory across consecutive jobs (2026-10-01)

Why: after switching to `large-v3-turbo`, the worker failed 3 of 8 uploaded jobs with
`Transcription failed: CUDA failed with error out of memory`, and long files got slower the longer the
worker had been running (45 min file: 5.5 min on a fresh worker, 16.5 min after 7 jobs).

## Setup
`python -m scripts.bench_memory` runs files one after another in a single process, like the worker, and
records at the start of each stage: `nvidia-smi` used memory (whole card, includes CTranslate2) and
`torch.cuda.memory_reserved()`. RTX 3050 Ti 4 GB (Windows, WDDM), worker stopped. Files in upload order:
3 FLEURS test meetings (40–58 s), `sample_meeting.wav` (53 s), ep4 5 min, ep8 5 min, ep4 (32 min),
ep8 (45 min).

## Results

| Version | Failed jobs | GPU memory between jobs | torch reserved (max) | ep4 32 min | ep8 45 min |
|---|---|---|---|---|---|
| Before (`627856d`) | **3/8** (jobs 6–8, transcription OOM / invalid device) | 2.1 → 3.85 GB | 9.9 GB | failed | failed |
| Cache release only (`SENTIMENT_DEVICE=cuda`) | 0/8 | 1.83 GB, flat | 0.65 GB | 203 s | 276 s |
| **Cache release + sentiment on CPU (`fd39cfe`)** | **0/8** | **1.30 GB, flat** | **0.11 GB** | 208 s | 284 s |

- PyTorch kept up to 9.9 GB reserved after diarizing a 5-minute file — more than the card has; Windows
  spills the excess to shared system memory, which explains the slowdowns, and CTranslate2 (Whisper)
  then cannot allocate. `torch.cuda.empty_cache()` before transcription and after diarization and gender
  keeps the reservation at ~0.1 GB between stages.
- Sentiment on the GPU holds ~540 MB permanently for ~0.5–6 s saved per file. Kept on CPU to leave
  headroom on the 4 GB card (e.g. for batched transcription).

## Time per stage, fixed version (job order as above)

| File | Audio | Transcription | Diarization | Gender | Sentiment | Total | Total / audio |
|---|---|---|---|---|---|---|---|
| ep4 5 min (job 5) | 300 s | 15 s | 61 s | 1 s | 1 s | 80 s | 0.27 |
| ep8 5 min (job 6) | 300 s | 18 s | 51 s | 0.4 s | 1 s | 72 s | 0.24 |
| ep4 32 min (job 7) | 1922 s | 94 s | 98 s | 1 s | 6 s | 208 s | 0.108 |
| ep8 45 min (job 8) | 2676 s | 141 s | 122 s | 1 s | 7 s | 284 s | 0.106 |

Estimate: **one hour of audio ≈ 6.5 minutes** on this GPU (transcription ~50 %, diarization ~43 %).
Short files are dominated by fixed diarization cost.
