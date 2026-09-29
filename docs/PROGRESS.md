# Tiến độ Bài 2

## Giai đoạn 0 — Nền móng và Docker (2026-09-29) — gần xong, còn chờ HF_TOKEN

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
- **Cần `HF_TOKEN` trong `.env`** và chấp nhận điều khoản các model pyannote trên huggingface.co
  (`pyannote/speaker-diarization-3.1`, `pyannote/segmentation-3.0`) → rồi chạy
  `scripts.run_pipeline` hết một file để đóng Giai đoạn 0.
- Whisper `base` sai nhiều trên file mẫu ("họp" → "học", "mắt" → "mắc") → chọn cỡ model ở Giai đoạn 6
  (với GPU 4 GB có thể dùng `small`/`medium` int8_float16).
- Sentiment: câu chào bình thường bị gắn "angry" với độ tin cậy 0.40 → nhãn negative→angry
  và câu có độ tin cậy thấp cần xem lại (chưa thuộc phạm vi giai đoạn nào).
- Cần vài file ghi âm cuộc họp thật (tiếng Việt, nhiều người) để đánh giá tóm tắt ở Giai đoạn 3.
- `torchaudio` chưa ghim phiên bản trong Dockerfile (đang ra 2.11.0) — ghim khi đổi layer torch lần sau.
