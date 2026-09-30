# Tiến độ Bài 2

## Giai đoạn 0 — Nền móng và Docker (2026-09-29) — gần xong, còn chờ quyền model pyannote

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

### Việc còn dở
- `HF_TOKEN` đã có (tài khoản `NMinh0926`), vào được `speaker-diarization-3.1` và `segmentation-3.0`.
  **Còn thiếu quyền `pyannote/speaker-diarization-community-1`**: pyannote 4.0.7 luôn tải PLDA từ repo này
  khi dựng pipeline (kể cả với 3.1). Điều khoản đã chấp nhận bằng tài khoản Gmail → cần thay `HF_TOKEN`
  bằng token của tài khoản đó (token cũ cũng cần thu hồi vì từng bị ghi thẳng trong một script), rồi chạy
  `scripts.run_pipeline` hết một file để đóng Giai đoạn 0.
- Whisper `base` sai nhiều trên file mẫu ("họp" → "học", "mắt" → "mắc") → chọn cỡ model ở Giai đoạn 6
  (với GPU 4 GB có thể dùng `small`/`medium` int8_float16).
- Sentiment: câu chào bình thường bị gắn "angry" với độ tin cậy 0.40 → nhãn negative→angry
  và câu có độ tin cậy thấp cần xem lại (chưa thuộc phạm vi giai đoạn nào).
- Audio thật: 2 tập Life Abroad Podcast (archive.org, CC BY-NC-ND 3.0; hội thoại 2 người, nam và nữ) trong
  `sample_data/real/` (không commit, không đưa vào image). Vẫn cần file họp nhiều người cho Giai đoạn 3.
- `torchaudio` chưa ghim phiên bản trong Dockerfile (đang ra 2.11.0) — ghim khi đổi layer torch lần sau.

## Giai đoạn 1 — API, hàng đợi job, lưu trữ (2026-09-30) — xong phần code, chờ quyền pyannote để chạy thật hết pipeline

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

### Việc còn dở
- Tiêu chí "5 file chạy xong" với model thật: chờ token mới có quyền `community-1`.
- `UPLOAD_DIR` (config, `main.py`) không còn được dùng vì file gốc lưu trên S3 — xoá khi dọn config.
