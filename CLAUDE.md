# CLAUDE.md

## Dự án
Hệ thống xử lý ghi âm cuộc họp tiếng Việt.
Luồng: upload audio (WAV/MP3/M4A) → chuẩn hoá 16 kHz mono → faster-whisper (chuyển giọng nói thành chữ,
mốc thời gian từng từ) → pyannote (tự tách người nói, tự đếm số người) → gán người nói theo từng từ
→ gộp lượt nói → giới tính (nam/nữ) mỗi người nói → cảm xúc mỗi lượt (giọng + chữ) và cảm xúc chung
mỗi người nói → xem trên giao diện web (bấm câu để tua audio) → xuất TXT/SRT/JSON.
Kế hoạch từng giai đoạn: `docs/PLAN.md`. Tiến độ: `docs/PROGRESS.md`. Số liệu đo: `docs/benchmarks/`.

## Phạm vi đã chốt
- KHÔNG làm hỏi đáp về nội dung cuộc họp. KHÔNG tóm tắt bằng LLM (bỏ 2026-09-30). Xuất PDF tạm hoãn.
- Số người nói, giới tính và cảm xúc được nhận diện tự động, người dùng không phải nhập.
- Có giao diện web (React + Vite, như Bài 1).
- Kết nối hệ thống khác / cloud: chỉ thiết kế sẵn (API `/api/v1`, service tách khỏi HTTP,
  storage chuẩn S3, cấu hình qua env, xuất JSON), CHƯA làm API key, webhook.

## Quyết định đã chốt (không thay đổi nếu tôi chưa đồng ý)
- Hạ tầng như Bài 1: Docker Compose, PostgreSQL, SeaweedFS (S3; thay MinIO vì MinIO không còn image public).
- Không dùng LLM; KHÔNG dùng Gemini hay dịch vụ Google AI nào.
- Chép lời: faster-whisper `large-v3-turbo`, không VAD, `hallucination_silence_threshold` 2 s,
  `condition_on_previous_text=False` (đã đo: `docs/benchmarks/2026-09-30-asr-models.md`, `2026-10-01-decoding.md`).
- Giới tính: ECAPA-TDNN (JaesungHuh/voice-gender-classifier, MIT, mã trong `app/services/ecapa_gender.py`),
  nam khi p(nam) ≥ 0.2 (`docs/benchmarks/2026-10-01-speakers-gender.md`).
- Cảm xúc (6 loại: bình thường, vui vẻ, buồn, tức giận, ngạc nhiên, lo lắng): giọng emotion2vec+ large
  (`funasr`, đoạn ≤ 10 s, nhãn "disgusted" tính là bình thường) 0.6 + chữ PhoBERT UIT-VSMEC (HalogenFlo, MIT,
  từng câu) 0.4; cảm xúc chung của người nói = cảm xúc chiếm nhiều thời gian nói nhất
  (`docs/benchmarks/2026-10-01-emotion.md`).
- Model âm thanh (cả emotion2vec+) chạy trên GPU (RTX 3050 Ti, 4 GB) qua `DEVICE=cuda`; model cảm xúc chữ trên CPU;
  giải phóng cache GPU của PyTorch giữa các bước; worker xử lý 1 job một lúc.

## Quy tắc làm việc
- Làm theo từng giai đoạn. Đầu mỗi giai đoạn: đọc code liên quan, lập kế hoạch,
  CHỜ tôi duyệt rồi mới sửa.
- Không cài dependency mới hoặc đổi công nghệ lớn khi chưa hỏi tôi.
- Commit sau mỗi bước nhỏ đã chạy được, message tiếng Anh theo Conventional Commits.
- Viết/cập nhật test cho mọi phần mới; chạy toàn bộ test trước khi báo xong.
  Test không gọi model thật hay mạng (dùng mock); test cần model thật đánh dấu `integration`.
- Không đọc, sửa hay commit `.env`. Secret chỉ đi qua biến môi trường; cập nhật `.env.example`.
- Thay đổi liên quan hiệu năng hoặc chất lượng nhận diện: đo trước và sau, lưu kết quả vào `docs/benchmarks/`.
- Code có type hints, theo style sẵn có của project, không để lại code chết.
- Cuối mỗi giai đoạn: cập nhật `docs/PROGRESS.md`.
- Trả lời tôi bằng tiếng Việt; code, comment và commit bằng tiếng Anh.

## Lệnh thường dùng
Chạy từ thư mục gốc project bằng PowerShell. Python chỉ chạy trong Docker (`.venv` cũ đã hỏng, không dùng).
- Build và chạy: `docker compose up -d --build`
  - Giao diện web: http://127.0.0.1:8081 (8080 thuộc Bài 1)
  - API: http://127.0.0.1:8001/docs (8000 thuộc Bài 1). Kiểm tra: `curl.exe http://127.0.0.1:8001/api/health`.
- Test backend (dùng source hiện tại, không cần build lại image):
  `docker compose run --rm --no-deps -v "${PWD}:/app" api python -m pytest -q -p no:cacheprovider`
- Test frontend: chạy trong `docker compose build frontend` (typecheck + vitest), hoặc
  `docker run --rm -v "${PWD}/frontend:/app" -w /app node:22-alpine sh -c "npm ci && npm run typecheck && npm test"`
- Chạy thử pipeline một file:
  `docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.run_pipeline sample_data/sample_meeting.wav`
- Đánh giá (dừng worker trước: `docker compose stop worker`):
  - Chép lời (WER): `… api python -m scripts.bench_asr large-v3-turbo`
  - Giới tính / gán người nói: `… api python -m scripts.eval_gender clips [--holdout]` hoặc `meetings`
  - Bộ nhớ GPU qua nhiều job: `… api python -m scripts.bench_memory FILE …`
  - Mất chữ trong hội thoại: `… api python -m scripts.bench_transcript FILE… [--model M] [--fleurs]`
  - Cảm xúc từ chữ (UIT-VSMEC): `… api python -m scripts.bench_emotion_text MODEL…`
- Tính lại cảm xúc cho cuộc họp đã xử lý (dừng worker trước): `… api python -m scripts.recompute_emotions [ID…]`
- Dữ liệu test (không commit): `sample_data/real/` — podcast Life Abroad, cuộc họp FLEURS có đáp án nam/nữ
  (`test_meetings/`), clip FLEURS cho đánh giá (`fleurs/`, `fleurs_holdout/`).
- Xem log: `docker compose logs -f --tail=100 worker` (xử lý) hoặc `api`.
