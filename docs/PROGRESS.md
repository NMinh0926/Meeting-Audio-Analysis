# Tiến độ Bài 2

## Giai đoạn 0 — Nền móng và Docker (2026-09-29) — xong (2026-09-30)

### Đã làm
- Repo git riêng cho `Bai_2` (trước đó nằm lẫn trong repo `Documents`, chưa được theo dõi).
- Docker: `Dockerfile` (python 3.11, ffmpeg, torch 2.14 + torchcodec bản CUDA 12.6), `compose.yaml`
  gồm `postgres`, `seaweedfs`, `api` (GPU qua `deploy.resources…nvidia`, cổng 8001).
  `docker compose up -d` → cả 3 dịch vụ healthy, `/api/health` trả `ok`.
- Phiên bản thư viện: `requirements.txt` (thư viện chính) + `requirements.lock.txt` (pip freeze trong image).
- Sửa code:
  - diarization: pyannote 4 (`token=`, đọc `DiarizeOutput`, ưu tiên `exclusive_speaker_diarization`
    để mỗi thời điểm chỉ có một người nói); truyền waveform trong bộ nhớ thay vì đường dẫn file.
  - `DEVICE` áp dụng cho gender và sentiment (trước cố định CPU); `get_settings()` có cache;
    Settings bỏ qua biến lạ trong `.env`.
  - Model giới tính cũ (`…-oswg`) không còn trên Hugging Face → đổi sang `…-gender-recognition-librispeech`.
  - Đánh số lại log các bước trong pipeline.
- Test: viết `test_segment_merger.py`, `test_transcription.py`, thêm test pyannote 4 → **44 test qua**.
- Audio mẫu: `scripts/make_sample_meeting.py` tạo `sample_data/sample_meeting.wav` (53 s, 10 lượt,
  3 "người" bằng TTS `facebook/mms-tts-vie` đổi cao độ) + đáp án `sample_meeting.json`.
- `scripts/run_pipeline.py`: chạy pipeline một file, in kết quả và thời gian từng bước.

### Quyết định
- torch bản CUDA 12.6 (`cu126`): CTranslate2 của faster-whisper cần cuBLAS/cuDNN của CUDA 12.
  `torchcodec` trên PyPI build cho CUDA 13 → không nạp được → cài bản `cu126` từ index PyTorch.
- Image ~13 GB (chủ yếu thư viện CUDA). Chấp nhận để chạy GPU.

### Số liệu đo (GPU RTX 3050 Ti, file mẫu 53 s)
| Bước | Thời gian | Ghi chú |
|---|---|---|
| Chuẩn hoá audio | 0.2 s | |
| Whisper `base` | 5.2 s | model đã có trong cache |
| Giới tính (3 người) | 0.9 s | |
| Bộ nhớ GPU đỉnh | ~525 MB | Whisper + sentiment |

### Đóng giai đoạn (2026-09-30)
- `HF_TOKEN` mới có quyền cả `speaker-diarization-3.1`, `segmentation-3.0` và `speaker-diarization-community-1`
  (pyannote 4.0.7 luôn tải PLDA từ `community-1` khi dựng pipeline, kể cả với 3.1).
- `scripts.run_pipeline` chạy hết 7 bước trên đoạn podcast 5 phút trong container GPU: 2 người nói, 19 lượt.

### Việc còn dở
- Whisper `base` sai nhiều trên file mẫu ("họp" → "học", "mắt" → "mắc") → chọn cỡ model ở Giai đoạn 6
  (với GPU 4 GB có thể dùng `small`/`medium` int8_float16).
- Sentiment: câu chào bình thường bị gắn "angry" với độ tin cậy 0.40 → nhãn negative→angry
  và câu có độ tin cậy thấp cần xem lại (chưa thuộc phạm vi giai đoạn nào).
- Audio thật: 2 tập Life Abroad Podcast (archive.org, CC BY-NC-ND 3.0; hội thoại 2 người, nam và nữ) trong
  `sample_data/real/` (không commit, không đưa vào image). Vẫn cần file họp nhiều người cho Giai đoạn 3.
- `torchaudio` chưa ghim phiên bản trong Dockerfile (đang ra 2.11.0) — ghim khi đổi layer torch lần sau.

## Giai đoạn 1 — API, hàng đợi job, lưu trữ (2026-09-30) — xong

### Đã làm
- Thêm dependency `psycopg[binary]` 3.3.6, `boto3` 1.43.105; ghim `SQLAlchemy` 2.1.1, `alembic` 1.20.0.
- DB (SQLAlchemy + Alembic, migration `0001`): `meetings` (trạng thái `queued/processing/done/failed`,
  bước đang chạy, lỗi, số lần chạy, `seq` giữ thứ tự upload), `speakers` (nhãn gốc + tên hiển thị để đổi tên),
  `segments`. Bảng `summaries` để sang Giai đoạn 3.
- Storage: `S3Storage` (upload/download dạng stream, lỗi → `StorageError` / `ObjectNotFoundError`).
- API `/api/v1/meetings`: `POST` nhiều file (kiểm tra đuôi, rỗng, `MAX_UPLOAD_MB`; lỗi giữa chừng thì
  xoá file đã lưu), `GET` danh sách (lọc trạng thái, phân trang), `GET /{id}` (kèm người nói),
  `POST /{id}/retry` (chỉ job `failed`), `DELETE /{id}` (409 khi đang chạy). Logic ở `app/services/meetings.py`.
- Worker `python -m app.worker`: lấy job bằng `SELECT … FOR UPDATE SKIP LOCKED` theo thứ tự upload,
  cập nhật `current_stage` từng bước, lưu kết quả; lỗi → `failed` + `error_code`/`error_message`;
  khởi động lại thì job kẹt ở `processing` quay về hàng đợi. Model nạp một lần.
- Pipeline: callback `on_stage`; xoá file WAV chuẩn hoá sau khi chạy (trước đây để lại trong `data/temp`).
- Compose: service `init` (chạy `alembic upgrade head` rồi thoát), `worker`; `api` và `worker` chờ `init`.
- Test: 84 test qua (thêm test storage, API, hàng đợi: 2 phiên lấy job không trùng, 5 file chạy hết,
  thứ tự upload, job lỗi chạy lại được, job kẹt được phục hồi). Test DB dùng `meeting_test`.

### Quyết định
- Thứ tự hàng đợi theo cột `seq` (identity), không theo `created_at`: các file trong cùng một request
  có chung `created_at` (thời điểm transaction).
- GPU vẫn cấp cho cả `api` và `worker` (anchor chung): lệnh `compose run api … run_pipeline` cần GPU;
  server `api` không nạp model nên không chiếm bộ nhớ GPU.
- Worker không có healthcheck (không có cổng HTTP); `restart: unless-stopped` lo trường hợp worker chết.

### Kiểm tra thật trên stack (GPU)
- Upload 5 file trong một request → worker chạy lần lượt đúng thứ tự; cả 5 dừng ở bước diarization với
  `DiarizationError` (403 `community-1`, đúng như dự đoán). Retry → `attempts` = 2; xoá khi đang chạy → 409.
- Whisper chỉ nạp ở job đầu: job sau chạy bước chuyển giọng nói trong ~2.4 s cho file 53 s.
- **Tiêu chí đóng giai đoạn** (sau khi có token mới): 5 file gửi trong một request (53 s, 2 đoạn 5 phút,
  tập 32 phút, tập 45 phút) → cả 5 `done`, không lỗi. Tổng 87.5 phút audio xử lý trong 75.5 phút
  (0.86 × độ dài audio). Chi tiết từng bước: `docs/benchmarks/2026-09-30-baseline-gpu.md`.

### Việc còn dở
- Bước tách người nói chiếm 58–82 % thời gian mỗi job; GPU 4 GB đầy (đỉnh 3932 MB) khi cả 4 model nằm trên
  GPU → cùng một bước chạy nhanh chậm thất thường. Xử lý ở Giai đoạn 6.
- Số người nói chưa chuẩn: file mẫu TTS 3 giọng → 5 người; tập 4 (2 người) → 3 người. Kiểm tra lại khi có
  trang xem bản ghi (Giai đoạn 2) và khi chỉnh diarization (Giai đoạn 6).

## Giai đoạn 2 — Xem lại nội dung (2026-09-30)

### Đã làm
- Bảng `utterances` (migration `0002`): các câu Whisper (đã gắn người nói) bên trong mỗi lượt nói đã gộp.
  Lý do: lượt nói gộp dài tới 222 s / 3449 ký tự (tập 8) — không dùng được cho SRT hay tua/highlight câu.
  Bước gộp (`segment_merger`) giữ lại câu gốc; worker lưu cả lượt nói và câu.
- `GET /api/v1/meetings/{id}/transcript`: người nói (tên hiển thị) + lượt nói theo thời gian, mỗi lượt kèm câu.
  Chỉ khi `done` (khác → 409).
- `GET …/{id}/audio`: file gốc stream từ S3, hỗ trợ `Range` một khoảng (`a-b`, `a-`, `-n`) → 206;
  ngoài file → 416 `bytes */size`; nhiều khoảng / sai cú pháp → trả cả file (RFC 9110 cho phép).
  Dùng được cả khi chưa xử lý xong. File gốc mất trên S3 → 404.
- `PATCH …/{id}/speakers/{speaker_id}`: đổi tên hiển thị (bỏ khoảng trắng thừa, 1–100 ký tự).
- `GET …/{id}/export?format=txt|srt` (`app/services/export.py`, Giai đoạn 4 thêm `pdf`): TXT theo lượt nói,
  SRT mỗi câu một cue; tên file tải về giữ tiếng Việt (`filename*=UTF-8''…`) kèm tên ASCII dự phòng.
- Dọn `UPLOAD_DIR` (không còn dùng từ khi file gốc lưu trên S3).
- Test: 144 test qua.

### Quyết định
- Kích thước file cho `Range` lấy từ `meetings.size_bytes` (ghi lúc upload), không gọi `HEAD` lên S3.

### Kiểm tra thật trên stack
- Audio tập 4 (46 MB) qua SeaweedFS: không `Range` → 200 cả file; `bytes=0-1023`, `bytes=46000000-`, `bytes=-500`
  → 206 đúng `Content-Range`; ngoài file → 416; byte trả về khớp file gốc.
- `sample_meeting.wav` xử lý lại: 8 lượt nói, 10 câu; đổi tên `SPEAKER_00` → "Chủ trì" hiện ngay trong TXT;
  SRT tải về đúng tên file, mỗi câu một cue.
- 5 cuộc họp cũ (chưa có câu) đã xoá và upload lại để có `utterances`.

### Việc còn dở
- Gửi JSON có dấu tiếng Việt bằng `curl -d` trong Git Bash bị hỏng mã hoá (lỗi phía shell, API đúng) —
  dùng `--data-binary @file.json` khi thử tay.

## Đổi kế hoạch (2026-09-30)
Bỏ tóm tắt bằng LLM (và Ollama); xuất PDF tạm hoãn. Giai đoạn 3 mới: trích xuất dữ liệu + nhận diện nam/nữ;
Giai đoạn 4: giao diện web; Giai đoạn 5: tăng tốc. Xem `docs/PLAN.md`. CLAUDE.md vẫn còn dòng LLM/PDF —
chờ bạn đồng ý mới sửa.

## Giai đoạn 3 — Trích xuất dữ liệu và nhận diện nam/nữ (2026-10-01) — xong

### Đã làm
- Giới tính trong mọi đầu ra: TXT (`Chị Lan (Nữ, 98%)`, mỗi lượt `Tên (Nữ): …`), SRT, thêm `format=json`.
- Chép lời: `base` → **`large-v3-turbo`**. WER trên 120 clip FLEURS: 25.9 % → **5.9 %**
  (`docs/benchmarks/2026-09-30-asr-models.md`; PhoWhisper small/medium kém hơn: 12.7 % / 9.5 %).
- Bỏ VAD (làm mất nguyên câu giữa 2 người nói); chống câu bịa ("Hãy subscribe cho kênh …") bằng
  `hallucination_silence_threshold` 2 s + giải mã từng đoạn độc lập: 10 cuộc họp ghép 0/40 câu mất, 0 câu bịa
  (`docs/benchmarks/2026-10-01-decoding.md`).
- Gán người nói **theo từng từ** (`word_timestamps`), tách câu khi đổi người nói, làm mượt từ lẻ ≤ 0.5 s.
  Câu "lẫn" 2 người trong 6 cuộc họp ghép: 9/32 → **0/24**; gán đúng 94.1 % → **100 %**.
- Giới tính: model cũ (wav2vec2 LibriSpeech) nhận sai 34/60 giọng nam Việt thành nữ → thay bằng
  **ECAPA-TDNN** (JaesungHuh, MIT, chép mã vào `app/services/ecapa_gender.py`) với ngưỡng p(nam) ≥ 0.2,
  độ tin cậy < 0.55 → "Không rõ". Tập chỉnh ngưỡng 120/120, **tập held-out 119/120 (1 không rõ, 0 sai)**,
  cuộc họp ghép 22/24 (2 không rõ, 0 sai). Mỗi người nói chấm tối đa 60 s theo khúc ≤ 10 s:
  bước giới tính 5.6–54.9 s → 0.3–1.7 s (`docs/benchmarks/2026-10-01-speakers-gender.md`).
- Tập 45 phút: 37 phút 42 s → 5 phút 31 s khi worker vừa khởi động, nhưng 16.5 phút sau 7 job liên tiếp
  (tách người nói 2.2 → 12.6 phút): model dồn lại làm đầy GPU 4 GB — xử lý ở Giai đoạn 5.
- Script đánh giá: `scripts/bench_asr.py` (WER), `scripts/eval_gender.py` (fetch/clips/meetings, held-out),
  `scripts/bench_gender.py`. Dữ liệu FLEURS và cuộc họp ghép trong `sample_data/real/` (không commit).
- Test: 178 test qua.

### Việc còn dở
- Tách người nói hay gộp 2 giọng ngắn (~10 s) thành 1 (cuộc họp ghép: tìm ra 2–4 người thay vì 4).
- Còn lỗi chép lời hội thoại: "hồ sơ" → "bộ sơ", "trường tư" → "trường 4", tên riêng ("DELF" → "Danf").
- Cảm xúc chưa đánh giá (vẫn hay gắn "angry").

## Giai đoạn 4 — Giao diện web (2026-09-30) — xong

### Đã làm
- `frontend/` React 19 + Vite 7 + TypeScript + Tailwind 4 (cùng bộ với Bài 1, không thêm thư viện router).
  Service `frontend` (nginx, chuyển `/api` sang `api`) ở **http://127.0.0.1:8081**.
- Danh sách: kéo thả upload nhiều file (thanh tiến độ), trạng thái + bước đang chạy tự cập nhật, chạy lại, xoá.
- Chi tiết: trình phát audio cố định trên cùng; người nói với nhãn Nam/Nữ + độ tin cậy, bấm tên để đổi;
  bản ghi theo lượt → câu: **bấm câu thì audio tua tới đầu câu và phát**, câu đang phát tô vàng, tự cuộn;
  tải TXT/SRT/JSON.
- Test: vitest 30 test (định dạng, tìm câu đang phát, route, lỗi API); typecheck + test chạy trong build Docker.
- Kiểm tra bằng Chromium headless (Playwright trong container): bấm câu #45 (165.8 s) → audio 167.1 s sau
  1.5 s phát, câu được tô sáng, không lỗi console.

## Giai đoạn 5 — Tăng tốc và benchmark (2026-10-01) — xong

### Đã làm
- **Lỗi hết bộ nhớ GPU**: sau vài job, Whisper báo `CUDA out of memory` (3/8 job lỗi) vì PyTorch giữ tới
  9.9 GB cache sau bước tách người nói (Windows tràn sang RAM → chậm dần, rồi CTranslate2 hết chỗ).
  Sửa: `torch.cuda.empty_cache()` trước chép lời và sau tách người nói / giới tính (`app/core/gpu.py`);
  model cảm xúc chạy trên CPU (`SENTIMENT_DEVICE`, giữ thêm ~540 MB GPU nếu để trên GPU).
  8 job liên tiếp: 0 lỗi, bộ nhớ ổn định 1.3 GB (`docs/benchmarks/2026-10-01-gpu-memory.md`).
- **Câu trả lời của kế hoạch**:
  - File 1 giờ ≈ **6.5 phút** (0.106 × độ dài; chép lời ~45–50 %, tách người nói ~43 %).
  - Tải: 10 file gửi song song → upload 4.5 s, 0 lỗi, mỗi job 5 phút mất 71 s đều đặn, xong cả 10 sau
    12 phút 31 s; API vẫn 10–40 ms. Máy xử lý ~4 giờ audio ngắn hoặc ~9 giờ audio dài mỗi giờ; vượt mức đó
    thì hàng đợi dài dần (`docs/benchmarks/2026-10-01-load.md`).
- Thử và **không áp dụng** (`docs/benchmarks/2026-10-01-diarization-batching.md`):
  - Hạ ngưỡng gộp người nói pyannote: tách đúng hơn ở cuộc họp ghép nhưng từ 0.60 tách thừa podcast thật.
  - `BatchedInferencePipeline`: chép lời nhanh 2.5–2.8× nhưng mất 2–4/52 câu với mọi cấu hình VAD.
- Script: `scripts/bench_memory.py`. Test: 182 test qua (thêm test dọn bộ nhớ, thứ tự gọi, thiết bị
  model cảm xúc — test này trước đó lỡ nạp model thật, đã sửa bằng module giả).

### Việc còn dở / ý tưởng
- Cho người dùng nhập số người nói (pyannote `num_speakers`) khi biết trước — cách chắc nhất để không gộp
  hai giọng giống nhau.
- Cảm xúc chưa được đánh giá; tách người nói vẫn gộp giọng ngắn cùng giới.
- `CLAUDE.md` còn dòng LLM/Ollama/PDF — chờ bạn đồng ý mới sửa.
