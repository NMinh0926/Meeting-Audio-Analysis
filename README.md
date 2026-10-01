# Meeting Audio Analysis

Hệ thống xử lý ghi âm cuộc họp tiếng Việt: tải file lên, nhận lại bản ghi có mốc thời gian, biết **ai nói**,
người đó **nam hay nữ**, và **cảm xúc** của từng lượt nói. Bản ghi xem trên web (bấm câu để nghe đúng chỗ đó)
và xuất được TXT, SRT, JSON. Model chạy ngay trên máy của bạn: ghi âm và bản ghi không gửi đi đâu (mạng chỉ dùng
để tải model lần đầu).

## Tính năng

- **Chuyển giọng nói thành chữ** bằng faster-whisper `large-v3-turbo`, có mốc thời gian từng từ.
- **Tự tách và đếm người nói** (pyannote), gán người nói theo từng từ nên câu có hai người nói được tách đúng chỗ.
- **Nam / nữ** cho mỗi người nói (ECAPA-TDNN), kèm độ tin cậy; "Không rõ" khi không chắc.
- **Cảm xúc** mỗi lượt nói — bình thường, vui vẻ, buồn, tức giận, ngạc nhiên, lo lắng — kết hợp giọng nói
  (emotion2vec+) và nội dung (PhoBERT tiếng Việt), và **cảm xúc chung** của mỗi người nói, ví dụ
  *"Người nói 1 – Nữ – Vui vẻ"*.
- **Giao diện web**: kéo thả nhiều file, theo dõi tiến độ, bấm câu để tua audio, câu đang phát được tô sáng
  và tự cuộn theo; nút ±5 giây, tốc độ phát, phím tắt; đổi tên người nói.
- **Xuất** TXT (đọc), SRT (phụ đề), JSON (cho hệ thống khác).
- **API REST** `/api/v1` có tài liệu Swagger; hàng đợi job trong PostgreSQL, file gốc trên kho S3.

## Kết quả đo

Đo trên RTX 3050 Ti 4 GB. Chi tiết và cách đo trong [`docs/benchmarks/`](docs/benchmarks/).

| Hạng mục | Kết quả |
|---|---|
| Chép lời (WER, 120 câu đọc FLEURS tiếng Việt) | **5.9 %** (Whisper `base`: 25.9 %) |
| Bỏ sót lời trong hội thoại thật (podcast 32–45 phút) | 1.2–5.4 % thời lượng có tiếng nói |
| Nam / nữ (240 giọng FLEURS) | **239/240 đúng**, 1 "không rõ", 0 nhầm giới |
| Gán người nói theo từ (cuộc họp ghép 4 giọng) | 0/24 câu bị lẫn hai người |
| Cảm xúc từ chữ (tập test UIT-VSMEC, 6 nhãn) | 68 % (model cũ: 33 %) |
| Gắn nhầm cảm xúc trên giọng đọc bình thản | 5 % (6/120) |
| Tốc độ | ~**7 phút** cho 1 giờ ghi âm; file 5 phút ≈ 85–90 giây |
| Bộ nhớ GPU | ổn định ~2 GB giữa các job |

## Yêu cầu

- Docker Desktop (Windows dùng WSL2) hoặc Docker Engine + Docker Compose.
- GPU NVIDIA **≥ 4 GB** VRAM, driver mới và hỗ trợ GPU cho Docker (NVIDIA Container Toolkit).
- Khoảng **20 GB** ổ đĩa: image ~13.5 GB, model tải lần đầu ~4 GB.
- Tài khoản Hugging Face và token đọc (*read*), đã bấm đồng ý điều khoản của:
  [`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1),
  [`pyannote/segmentation-3.0`](https://huggingface.co/pyannote/segmentation-3.0),
  [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1).

## Cài đặt và chạy

```powershell
git clone https://github.com/NMinh0926/Meeting-Audio-Analysis.git
cd Meeting-Audio-Analysis
copy .env.example .env      # Linux/macOS: cp .env.example .env
```

Mở `.env`, điền `HF_TOKEN` và đổi các mật khẩu `change_me…`. **Không commit `.env`.**

```powershell
docker compose up -d --build
```

- Giao diện web: http://127.0.0.1:8081
- API và tài liệu: http://127.0.0.1:8001/docs — kiểm tra: `curl http://127.0.0.1:8001/api/health`

Lần chạy đầu worker tải model (~4 GB) nên job đầu tiên chậm hơn. Xem tiến độ:
`docker compose logs -f --tail=100 worker`.

Dừng: `docker compose down` (dữ liệu và model vẫn giữ trong volume Docker).

## Sử dụng

1. Kéo thả file WAV / MP3 / M4A vào trang chủ (chọn được nhiều file, tối đa 500 MB mỗi file).
2. Chờ trạng thái **Xong** — các bước đang chạy hiện ngay trong danh sách.
3. Mở cuộc họp: bấm một câu để nghe từ chỗ đó; bấm tên người nói để đổi tên.

| Phím | Tác dụng |
|---|---|
| Space | Phát / dừng |
| ← / → | Lùi / tới 5 giây |
| ↑ / ↓ | Câu trước / câu sau |

Khi bật *Tự cuộn*, trang theo câu đang phát; tự cuộn ra chỗ khác thì trang dừng theo và hiện nút
**Về câu đang phát** để quay lại.

## API

| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| `POST` | `/api/v1/meetings` | Tải lên một hay nhiều file (`multipart`, trường `files`); trả 202 và xếp hàng |
| `GET` | `/api/v1/meetings` | Danh sách, mới nhất trước (`status`, `limit`, `offset`), kèm người nói |
| `GET` | `/api/v1/meetings/{id}` | Trạng thái, bước đang chạy, người nói |
| `GET` | `/api/v1/meetings/{id}/transcript` | Người nói (giới tính, cảm xúc chung) và các lượt nói theo câu |
| `GET` | `/api/v1/meetings/{id}/audio` | File gốc, hỗ trợ `Range` để tua |
| `GET` | `/api/v1/meetings/{id}/export?format=txt\|srt\|json` | Tải bản ghi |
| `PATCH` | `/api/v1/meetings/{id}/speakers/{speaker_id}` | Đổi tên người nói |
| `POST` | `/api/v1/meetings/{id}/retry` | Chạy lại job lỗi |
| `DELETE` | `/api/v1/meetings/{id}` | Xoá file và kết quả |

## Kiến trúc

```
Trình duyệt ──► frontend (React + Vite, nginx :8081) ──/api──► api (FastAPI :8001)
                                                              │      │
                                                      PostgreSQL   SeaweedFS (S3)
                                                       (job, kết quả)  (file gốc)
                                                              ▲
                                     worker (GPU, 1 job một lúc, SELECT … FOR UPDATE SKIP LOCKED)
```

Các bước của worker: chuẩn hoá 16 kHz mono → chép lời → tách người nói → gán người nói theo từ → gộp lượt
nói → giới tính mỗi người → cảm xúc mỗi lượt (giọng ≤ 10 s mỗi đoạn trên GPU, chữ từng câu trên CPU).
Bộ nhớ GPU của PyTorch được giải phóng giữa các bước để Whisper (CTranslate2) luôn có chỗ.

```
app/          FastAPI, worker, pipeline và các service (không phụ thuộc HTTP)
frontend/     Giao diện React + TypeScript + Tailwind
migrations/   Alembic
scripts/      Đo đạc, đánh giá và tiện ích (bench_*, eval_gender, recompute_emotions, …)
tests/        pytest (model và mạng được giả lập)
docs/         Kế hoạch, tiến độ, số liệu đo
```

## Cấu hình chính (`.env`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HF_TOKEN` | — | Token Hugging Face (bắt buộc, cho pyannote) |
| `WHISPER_MODEL` | `large-v3-turbo` | Model chép lời |
| `GENDER_MALE_THRESHOLD` | `0.2` | Ngưỡng p(nam) để kết luận nam |
| `GENDER_MIN_CONFIDENCE` | `0.55` | Dưới mức này ghi "Không rõ" |
| `EMOTION_VOICE_WEIGHT` | `0.6` | Tỉ trọng giọng nói khi kết hợp với chữ |
| `EMOTION_MIN_MARGIN` | `0.15` | Cảm xúc phải hơn "bình thường" bao nhiêu mới được gắn |
| `MAX_UPLOAD_MB` | `500` | Giới hạn mỗi file |

Danh sách đầy đủ: [`.env.example`](.env.example) và [`app/core/config.py`](app/core/config.py).

## Kiểm thử

```powershell
# Backend (dùng mã nguồn hiện tại, không cần build lại)
docker compose run --rm --no-deps -v "${PWD}:/app" api python -m pytest -q -p no:cacheprovider
# Frontend (typecheck + vitest)
docker run --rm -v "${PWD}/frontend:/app" -w /app node:22-alpine sh -c "npm ci && npm run typecheck && npm test"
```

Các script đo (`scripts/bench_*.py`, `scripts/eval_gender.py`) cần dữ liệu tải riêng vào `sample_data/real/`
(không có trong repo); cách dùng ghi ở đầu mỗi script.

## Giới hạn đã biết

- Chỗ nói chen nhạc nền, tên riêng và từ dễ nhầm đôi khi vẫn sai hoặc bị bỏ.
- Hai giọng cùng giới nói rất ngắn có thể bị gộp thành một người.
- Phần cảm xúc từ giọng nói chưa được đo độ chính xác trên tiếng Việt (chưa có dữ liệu gắn nhãn); trọng số
  kết hợp là ước lượng.
- Chỉ chạy một job một lúc trên một GPU; nhiều file sẽ xếp hàng.

## Model và dữ liệu bên thứ ba

| Thành phần | Nguồn | Giấy phép |
|---|---|---|
| Chép lời | [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) (bản CTranslate2 [mobiuslabsgmbh/faster-whisper-large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo)) qua faster-whisper | MIT (model gốc) |
| Tách người nói | [pyannote speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1), segmentation-3.0; PLDA từ [community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) | MIT; community-1: CC BY 4.0 (cần đồng ý điều khoản) |
| Giới tính | [JaesungHuh/voice-gender-classifier](https://huggingface.co/JaesungHuh/voice-gender-classifier) (mã chép vào `app/services/ecapa_gender.py`) | MIT |
| Cảm xúc từ giọng | [emotion2vec/emotion2vec_plus_large](https://huggingface.co/emotion2vec/emotion2vec_plus_large) qua [FunASR](https://github.com/modelscope/FunASR) | [FunASR Model License](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE) (ghi nguồn) |
| Cảm xúc từ chữ | [HalogenFlo/phobert-vsmec-emotion-recognition](https://huggingface.co/HalogenFlo/phobert-vsmec-emotion-recognition) | MIT |
| Audio mẫu `sample_data/sample_meeting.wav` | Tạo bằng [facebook/mms-tts-vie](https://huggingface.co/facebook/mms-tts-vie) | CC BY-NC 4.0 |
| Dữ liệu đánh giá (không kèm repo) | [FLEURS](https://huggingface.co/datasets/google/fleurs) (CC BY 4.0), [UIT-VSMEC](https://huggingface.co/datasets/tridm/UIT-VSMEC) | theo nguồn |
