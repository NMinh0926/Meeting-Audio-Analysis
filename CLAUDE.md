# CLAUDE.md

## Dự án
Hệ thống xử lý ghi âm cuộc họp tiếng Việt.
Luồng: upload audio (WAV/MP3/M4A) → chuẩn hoá 16 kHz mono → faster-whisper (chuyển giọng nói thành chữ)
→ pyannote (tách người nói) → ghép theo thời gian → gộp lượt nói → giới tính / cảm xúc
→ tóm tắt bằng LLM → xuất PDF, thao tác trên giao diện web.
Kế hoạch từng giai đoạn: `docs/PLAN.md`. Tiến độ: `docs/PROGRESS.md`.

## Phạm vi đã chốt
- KHÔNG làm hỏi đáp về nội dung cuộc họp.
- Có giao diện web (React + Vite, như Bài 1).
- Kết nối hệ thống khác / cloud: chỉ thiết kế sẵn (API `/api/v1`, service tách khỏi HTTP,
  storage chuẩn S3, cấu hình qua env), CHƯA làm API key, webhook.

## Quyết định đã chốt (không thay đổi nếu tôi chưa đồng ý)
- Hạ tầng như Bài 1: Docker Compose, PostgreSQL, SeaweedFS (S3; thay MinIO vì MinIO không còn image public).
- LLM: Ollama `qwen2.5:7b` chạy trên máy host Windows, app trong Docker gọi qua `host.docker.internal`.
  KHÔNG dùng Gemini hay dịch vụ Google AI nào.
- Xuất PDF: WeasyPrint (HTML → PDF), font có dấu tiếng Việt nhúng sẵn.
- Model chạy trên GPU (RTX 3050 Ti, 4 GB) qua `DEVICE=cuda`; worker xử lý 1 job một lúc.

## Quy tắc làm việc
- Làm theo từng giai đoạn. Đầu mỗi giai đoạn: đọc code liên quan, lập kế hoạch,
  CHỜ tôi duyệt rồi mới sửa.
- Không cài dependency mới hoặc đổi công nghệ lớn khi chưa hỏi tôi.
- Commit sau mỗi bước nhỏ đã chạy được, message tiếng Anh theo Conventional Commits.
- Viết/cập nhật test cho mọi phần mới; chạy toàn bộ test trước khi báo xong.
  Test không gọi model thật, LLM hay mạng (dùng mock); test cần model thật đánh dấu `integration`.
- Không đọc, sửa hay commit `.env`. Secret chỉ đi qua biến môi trường; cập nhật `.env.example`.
- Thay đổi liên quan hiệu năng: đo trước và sau, lưu kết quả vào `docs/benchmarks/`.
- Code có type hints, theo style sẵn có của project, không để lại code chết.
- Cuối mỗi giai đoạn: cập nhật `docs/PROGRESS.md`.
- Trả lời tôi bằng tiếng Việt; code, comment và commit bằng tiếng Anh.

## Lệnh thường dùng
Chạy từ thư mục gốc project bằng PowerShell. Python chỉ chạy trong Docker (`.venv` cũ đã hỏng, không dùng).
- Build và chạy: `docker compose up -d --build` → http://127.0.0.1:8001/docs
  (cổng 8000 thuộc Bài 1). Kiểm tra: `curl.exe http://127.0.0.1:8001/api/health`.
- Test (dùng source hiện tại, không cần build lại image):
  `docker compose run --rm --no-deps -v "${PWD}:/app" api python -m pytest -q -p no:cacheprovider`
- Tạo audio mẫu: `docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.make_sample_meeting`
- Chạy thử pipeline một file:
  `docker compose run --rm --no-deps -v "${PWD}:/app" api python -m scripts.run_pipeline sample_data/sample_meeting.wav`
- Xem log: `docker compose logs -f --tail=100 api`
