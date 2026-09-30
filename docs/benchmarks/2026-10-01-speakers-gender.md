# Speaker attribution and gender recognition (2026-09-30 / 10-01)

RTX 3050 Ti 4 GB, worker stopped during every run. Data: FLEURS vi_vn train clips (CC BY 4.0) fetched by
`scripts.eval_gender`: a main set (60 male / 60 female, random) and a held-out set (60 / 60, first in
archive order, disjoint files). FLEURS has no speaker ids, so the two sets may share some voices.

## 1. Gender step time (`scripts.bench_gender`, stored turns as input)
Before = classify every turn whole (`6aacbb8`); after = ≤ 10 s pieces, ≤ 60 s per speaker (`f95a20d`).

| File | Audio (s) | Before (s) | After (s) |
|---|---|---|---|
| sample_meeting.wav | 53 | 1.9 | 1.7 |
| life_abroad_ep4_5min.mp3 | 300 | 5.6 | 1.5 |
| life_abroad_ep8_5min.mp3 | 300 | 27.2 | 1.1 |
| life_abroad_ep4.mp3 | 1922 | 54.9 | 2.3 |

Same labels except one low-confidence speaker in ep8 5 min (male 0.55 → female 0.65).

## 2. Speaker attribution (`scripts.eval_gender meetings --count 6 --gap 0.2`)
Six synthetic meetings, 4 speakers each (2 M / 2 F), 0.2 s between speakers. "Mixed" = utterances holding
more than 0.3 s of two different speakers; attribution = share of speech time labelled with the speaker
that owns most of its clip.

| Version | Mixed utterances | Attribution | Speakers found (truth 4) |
|---|---|---|---|
| base, sentence-level | 5/24 | 98.4% | 3, 3, 4, 3, 3, 1 |
| large-v3-turbo, sentence-level | 9/32 | 94.1% | 3, 4, 4, 3, 3, 3 |
| **large-v3-turbo + VAD, word-level** (`5b1bc39`) | **0/24** | **100.0%** | 3, 4, 4, 2, 2, 3 |

Turbo's longer sentences made mixing worse until words were assigned individually. Diarization still
often merges two of the ~10 s voices into one speaker.

## 3. Gender model, clip by clip (no diarization)

| Model | Set | Male | Female | Overall | Time (s) |
|---|---|---|---|---|---|
| alefiury wav2vec2-xlsr-53 LibriSpeech (current) | main | 26/60 | 60/60 | 71.7% | 29.5 |
| prithivMLmods Common-Voice-Gender-Detection | main | 35/60 | 59/60 | 78.3% | 25.0 |
| audeering wav2vec2-large-robust-24 age-gender (CC BY-NC-SA) | main | 30/60 | 60/60 | 75.0% | 28.4 |
| pitch: median F0 < 165 Hz | main | 59/60 | 37/60 | 80.0% | 5.7 |
| JaesungHuh ECAPA-TDNN VoxCeleb (MIT), argmax | main | 52/60 | 60/60 | 93.3% | 11.7 |
| ECAPA, male if p(male) > 0.2 | main | 60/60 | 60/60 | 100.0% | |
| ECAPA, argmax | **held-out** | 55/60 | 60/60 | 95.8% | |
| **ECAPA, male if p(male) > 0.2** | **held-out** | **60/60** | **60/60** | **100.0%** | |

- Every model leans female on Vietnamese male voices; the current one calls 57 % of them female, with
  high confidence, so a confidence floor cannot rescue it.
- ECAPA's errors are near the boundary: misclassified males have p(male) 0.25–0.50, every female < 0.1.
  The 0.2 threshold was picked on the main set and holds on the held-out set.
- Median F0: male p10/p50/p90 = 115/134/155 Hz, female 147/170/211 Hz. Adding a pitch rule to ECAPA
  made results worse (92–95 %).

## 4. After switching to ECAPA (`f2a4f76`, through the app code path)
`predict_speakers_gender`: ≤ 10 s pieces, ≤ 60 s per speaker, duration-weighted mean p(male),
male from 0.2, "unknown" when confidence < 0.55. The vendored model gives logits identical to upstream
(max difference 0.0 on 20 clips).

| Set | Correct | Wrong | Unknown |
|---|---|---|---|
| Main clips (60 M / 60 F) | 120 | 0 | 0 |
| Held-out clips (60 M / 60 F) | 119 | 0 | 1 (male) |
| 6 meetings, gap 0.2 s (24 speakers) | 22 | 0 | 2 |

The two unknowns in meetings are clips that diarization merged into a speaker of the other gender, so the
average lands near the threshold. Speaker attribution unchanged: 0/24 mixed utterances, 100 %.

Gender step on processed meetings (`scripts.bench_gender`): 0.3–1.7 s per file (was 1.1–2.3 s with the
wav2vec2 model after chunking, 5.6–54.9 s before). Life Abroad ep8 speaker SPEAKER_01 goes from
"unknown 0.53" to "male 0.95"; ep8 5 min SPEAKER_01 from "female 0.71" to "male 0.96" (the episode is two
men talking).
