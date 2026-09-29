# Kế hoạch Bài 2 — Hệ thống xử lý ghi âm cuộc họp

**Phạm vi:** upload nhiều file ghi âm → xử lý nhanh → lưu toàn bộ nội dung (ai nói, lúc nào, nói gì)
→ tóm tắt ý quan trọng → xuất PDF, tất cả trên giao diện web. Không có hỏi đáp.
Kết nối hệ thống khác chỉ thiết kế sẵn, chưa làm.

**Công nghệ:** FastAPI · PostgreSQL · SeaweedFS (S3) · Ollama `qwen2.5:7b` trên host · React + Vite
· WeasyPrint · Docker Compose.

## Giai đoạn 0 — Nền móng và Docker
- `compose.yaml`: postgres, seaweedfs, api (GPU qua `deploy.resources…nvidia`).
- Chốt `requirements.txt`; sửa diarization cho pyannote 4 (`token=`, `DiarizeOutput`);
  `DEVICE` áp dụng cho cả 4 model; cache `get_settings()`.
- Viết test còn trống (merger, transcription).
- Audio mẫu: `scripts/make_sample_meeting.py` (TTS, có đáp án); cần thêm file họp thật.
- **Xong khi:** compose chạy, test qua, pipeline chạy thật một file mẫu trong container.

## Giai đoạn 1 — API, hàng đợi job, lưu trữ
- Bảng `meetings`, `speakers`, `segments`, `summaries` (SQLAlchemy + Alembic).
- `POST /api/v1/meetings` (nhiều file), `GET /api/v1/meetings`, `GET /api/v1/meetings/{id}`,
  `POST …/{id}/retry`, `DELETE …/{id}`.
- Worker riêng lấy job bằng `SELECT … FOR UPDATE SKIP LOCKED`, nạp model một lần, 1 job một lúc,
  cập nhật bước hiện tại.
- **Xong khi:** gửi 5 file cùng lúc thì cả 5 chạy xong; job lỗi chạy lại được.

## Giai đoạn 2 — Xem lại nội dung
- `GET …/{id}/transcript`, `GET …/{id}/audio` (hỗ trợ HTTP Range), đổi tên người nói, xuất TXT/SRT.
- **Xong khi:** mở lại cuộc họp cũ thấy đủ bản ghi, nghe và tua được audio.

## Giai đoạn 3 — Tóm tắt
- Ollama qua API tương thích OpenAI; JSON gồm tóm tắt chung, chủ đề, quyết định,
  việc cần làm (ai, hạn), vấn đề còn bỏ ngỏ; mỗi ý có mốc thời gian nguồn (server kiểm tra).
- Cuộc họp dài: chia đoạn ~10 phút, tóm tắt từng đoạn rồi gộp.
- Bước riêng trong job, tạo lại được. Giải phóng bộ nhớ GPU trước khi gọi LLM.
- **Xong khi:** file 60 phút cho bản tóm tắt đúng ý chính, mốc thời gian dẫn đúng đoạn.

## Giai đoạn 4 — Xuất PDF
- Jinja2 + WeasyPrint, font Noto Sans. Gồm thông tin cuộc họp, tóm tắt, bảng việc cần làm,
  bản ghi đầy đủ. `GET …/{id}/export?format=pdf|txt|srt`.
- **Xong khi:** PDF hiển thị đúng tiếng Việt trên máy khác, file 60 phút xuất không lỗi.

## Giai đoạn 5 — Giao diện web (React + Vite)
- Upload kéo thả nhiều file; danh sách cuộc họp với trạng thái tự cập nhật, tìm kiếm, chạy lại, xóa.
- Trang chi tiết: trình phát audio, bản ghi theo người nói (bấm để tua, câu đang phát nổi bật),
  tóm tắt có mốc thời gian bấm được (highlight đoạn nguồn), đổi tên người nói, tải PDF/TXT/SRT.
- **Xong khi:** upload → theo dõi → xem → tải PDF mà không cần Swagger.

## Giai đoạn 6 — Tăng tốc và benchmark
- Đo thời gian từng bước, tỉ lệ thời gian xử lý / độ dài audio (CPU vs GPU).
- Thử: cỡ model Whisper, `BatchedInferencePipeline`, VAD, pyannote GPU, chạy song song.
- Đo WER tiếng Việt; đo tải 1/5/10/20 file đồng thời. Lưu vào `docs/benchmarks/`.
- **Xong khi:** trả lời được "file 1 giờ mất bao lâu" và "gửi bao nhiêu file thì nghẽn".

## Thiết kế sẵn cho kết nối sau này
- API có phiên bản `/api/v1` + OpenAPI; logic ở tầng service; storage chuẩn S3; LLM đổi bằng cấu hình.
- `docs/INTEGRATION.md`: việc cần làm khi mở kết nối (API key, webhook, CORS, rate limit).
