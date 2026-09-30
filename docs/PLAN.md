# Kế hoạch Bài 2 — Hệ thống xử lý ghi âm cuộc họp

**Phạm vi:** upload nhiều file ghi âm → xử lý nhanh → lưu toàn bộ nội dung (ai nói, lúc nào, nói gì,
giới tính người nói) → xem bản ghi trên giao diện web, bấm câu để tua audio → xuất TXT/SRT/JSON.
Không có hỏi đáp. **Không tóm tắt** (bỏ 2026-09-30). Xuất PDF tạm hoãn.
Kết nối hệ thống khác chỉ thiết kế sẵn, chưa làm.

**Công nghệ:** FastAPI · PostgreSQL · SeaweedFS (S3) · faster-whisper · pyannote · React + Vite
· Docker Compose.

## Giai đoạn 0 — Nền móng và Docker
- `compose.yaml`: postgres, seaweedfs, api (GPU qua `deploy.resources…nvidia`).
- Chốt `requirements.txt`; sửa diarization cho pyannote 4 (`token=`, `DiarizeOutput`);
  `DEVICE` áp dụng cho cả 4 model; cache `get_settings()`.
- Viết test còn trống (merger, transcription).
- Audio mẫu: `scripts/make_sample_meeting.py` (TTS, có đáp án); cần thêm file họp thật.
- **Xong khi:** compose chạy, test qua, pipeline chạy thật một file mẫu trong container.

## Giai đoạn 1 — API, hàng đợi job, lưu trữ
- Bảng `meetings`, `speakers`, `segments` (SQLAlchemy + Alembic).
- `POST /api/v1/meetings` (nhiều file), `GET /api/v1/meetings`, `GET /api/v1/meetings/{id}`,
  `POST …/{id}/retry`, `DELETE …/{id}`.
- Worker riêng lấy job bằng `SELECT … FOR UPDATE SKIP LOCKED`, nạp model một lần, 1 job một lúc,
  cập nhật bước hiện tại.
- **Xong khi:** gửi 5 file cùng lúc thì cả 5 chạy xong; job lỗi chạy lại được.

## Giai đoạn 2 — Xem lại nội dung
- `GET …/{id}/transcript`, `GET …/{id}/audio` (hỗ trợ HTTP Range), đổi tên người nói, xuất TXT/SRT.
- **Xong khi:** mở lại cuộc họp cũ thấy đủ bản ghi, nghe và tua được audio.

## Giai đoạn 3 — Trích xuất dữ liệu và nhận diện nam/nữ
- Giới tính trong mọi đầu ra: TXT (danh sách người nói + từng lượt), SRT, thêm `format=json` (toàn bộ dữ liệu).
- Nhận diện giới tính: mỗi người nói chấm tối đa ~60 s audio, mỗi lần ≤ ~10 s; độ tin cậy thấp → "Không rõ".
  Đo trước/sau, lưu `docs/benchmarks/`.
- Đo độ chính xác nam/nữ trên giọng thật có nhãn (FLEURS tiếng Việt, CC BY 4.0) ghép thành cuộc họp giả;
  test `integration`.
- **Xong khi:** file xuất có giới tính; có số liệu độ chính xác; bước giới tính không còn mất hàng trăm giây.

## Giai đoạn 4 — Giao diện web (React + Vite + TypeScript + Tailwind)
- Trang danh sách: kéo thả upload nhiều file; bảng cuộc họp với trạng thái/bước tự cập nhật; chạy lại, xoá.
- Trang chi tiết: trình phát audio (Range); người nói với nhãn Nam/Nữ, đổi tên; bản ghi theo lượt → câu:
  bấm câu thì audio tua tới đó và phát, câu đang phát nổi bật và tự cuộn; tải TXT/SRT/JSON.
- Service `frontend` (nginx phục vụ bản build, chuyển `/api` sang `api`), cổng 8081 (8080 thuộc Bài 1).
- **Xong khi:** upload → theo dõi → mở cuộc họp → bấm câu tua đúng chỗ → tải file, không cần Swagger.

## Giai đoạn 5 — Tăng tốc và benchmark
- Đo thời gian từng bước, tỉ lệ thời gian xử lý / độ dài audio (CPU vs GPU).
- Thử: cỡ model Whisper, `BatchedInferencePipeline`, VAD, pyannote GPU, chạy song song.
- Đo WER tiếng Việt; đo tải 1/5/10/20 file đồng thời. Lưu vào `docs/benchmarks/`.
- **Xong khi:** trả lời được "file 1 giờ mất bao lâu" và "gửi bao nhiêu file thì nghẽn".

## Thiết kế sẵn cho kết nối sau này
- API có phiên bản `/api/v1` + OpenAPI; logic ở tầng service; storage chuẩn S3; xuất JSON cho hệ thống khác.
- `docs/INTEGRATION.md`: việc cần làm khi mở kết nối (API key, webhook, CORS, rate limit).
