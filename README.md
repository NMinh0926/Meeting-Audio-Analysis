# Meeting Audio Analysis

Hệ thống xử lý ghi âm cuộc họp tiếng Việt: tải file lên và nhận lại bản ghi có mốc thời gian, biết ai nói,
người đó nam hay nữ, cảm xúc từng lượt nói; xem trên web (bấm câu để nghe đúng chỗ đó) và xuất TXT/SRT/JSON.

Dưới đây là hướng dẫn cài đặt từng bước để chạy trên máy của bạn, kể cả khi chưa từng dùng Docker.
Các bước dành cho **Windows 10/11** và đã được thử từ một bản clone mới với dữ liệu trống.

**Tóm tắt thời gian và dung lượng**

| Việc | Thời gian | Dung lượng |
|---|---|---|
| Cài driver, WSL2, Docker Desktop, Git (nếu chưa có) | 20–40 phút, có khởi động lại máy | ~5 GB |
| Build image lần đầu | 10–30 phút, tuỳ mạng (tải vài GB thư viện) | ~13.5 GB |
| Job đầu tiên (tải model) | thêm ~3 phút | ~4 GB |

---

## Bước 1. Kiểm tra máy

| Cần có | Tối thiểu | Ghi chú |
|---|---|---|
| Card đồ hoạ | **NVIDIA, ≥ 4 GB VRAM** | Không chạy được trên card AMD/Intel hay chỉ CPU với cấu hình hiện tại |
| RAM | 16 GB | Máy thử: 16 GB, Docker được cấp 8 GB |
| Ổ đĩa trống | ~25 GB | Image + model + dữ liệu |
| Hệ điều hành | Windows 10 (21H2+) / 11 64-bit | Máy thử: Windows 11 |

Xem card đồ hoạ: bấm `Ctrl + Shift + Esc` → **Performance** (Hiệu suất) → **GPU**: tên phải có chữ *NVIDIA*
và **Dedicated GPU memory** từ 4 GB trở lên.

## Bước 2. Cài phần mềm (Windows)

Mở **PowerShell** (bấm Start, gõ `PowerShell`). Các lệnh dưới đây gõ vào cửa sổ đó.

### 2.1. Driver NVIDIA
Tải driver mới nhất cho card của bạn tại https://www.nvidia.com/Download/index.aspx (hoặc qua ứng dụng
NVIDIA App / GeForce Experience), cài rồi khởi động lại máy. Kiểm tra:

```powershell
nvidia-smi
```

Phải thấy bảng có tên card và dòng `CUDA Version: 12.x` trở lên.

### 2.2. WSL2
Docker Desktop trên Windows chạy trong WSL2. Mở PowerShell **bằng quyền Administrator** (chuột phải →
*Run as administrator*):

```powershell
wsl --install
```

Khởi động lại máy khi được yêu cầu. Nếu máy đã có WSL, chạy `wsl --update` cho bản mới nhất.

### 2.3. Docker Desktop
1. Tải tại https://www.docker.com/products/docker-desktop/ và cài, giữ lựa chọn **Use WSL 2 instead of Hyper-V**.
2. Mở Docker Desktop, đợi biểu tượng cá voi ở góc màn hình báo *Engine running*.
3. Vào **Settings → General**, đảm bảo **Use the WSL 2 based engine** đang bật.

Trên Windows, GPU tự dùng được trong Docker khi đã có driver NVIDIA (bước 2.1); không cần cài thêm gì.
Kiểm tra Docker thấy GPU:

```powershell
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

Phải in ra bảng giống lệnh `nvidia-smi` ở bước 2.1. Sau đó có thể xoá image thử:
`docker rmi nvidia/cuda:12.6.3-base-ubuntu24.04`.

### 2.4. Git
Tải tại https://git-scm.com/download/win và cài với lựa chọn mặc định. Kiểm tra: `git --version`.

## Bước 3. Chuẩn bị tài khoản Hugging Face

Bước tách người nói dùng model pyannote, cần tài khoản Hugging Face (miễn phí) và token.

1. Đăng ký / đăng nhập tại https://huggingface.co.
2. Mở **lần lượt** 3 trang dưới đây, điền thông tin được hỏi (tên công ty/trường, mục đích) và bấm
   **Agree and access repository**:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
   - https://huggingface.co/pyannote/speaker-diarization-community-1

   Thiếu một trong ba trang là job sẽ lỗi ở bước *Tách người nói*.
3. Tạo token: ảnh đại diện → **Settings → Access Tokens → Create new token** → chọn loại **Read**, đặt tên
   bất kỳ → **Create token**. Sao chép chuỗi bắt đầu bằng `hf_…` và giữ kín (không gửi cho ai, không đưa lên
   GitHub).

## Bước 4. Tải mã nguồn

Chọn thư mục muốn đặt dự án (ví dụ `Documents`), rồi:

```powershell
cd $HOME\Documents
git clone https://github.com/NMinh0926/Meeting-Audio-Analysis.git
cd Meeting-Audio-Analysis
```

Từ đây trở đi, mọi lệnh đều chạy **trong thư mục `Meeting-Audio-Analysis`**.

## Bước 5. Tạo file cấu hình `.env`

```powershell
copy .env.example .env
notepad .env
```

Trong Notepad, sửa các dòng sau rồi lưu (`Ctrl + S`):

| Dòng | Điền gì |
|---|---|
| `HF_TOKEN=` | Token `hf_…` ở bước 3 |
| `POSTGRES_PASSWORD=` | Mật khẩu tuỳ ý cho cơ sở dữ liệu (chỉ chữ và số cho dễ) |
| `S3_ACCESS_KEY=` | Tên đăng nhập tuỳ ý cho kho file |
| `S3_SECRET_KEY=` | Mật khẩu tuỳ ý cho kho file, **ít nhất 8 ký tự** |

Các dòng khác giữ nguyên. Lưu ý:
- **Đặt `POSTGRES_PASSWORD` trước lần chạy đầu tiên.** Cơ sở dữ liệu ghi nhận mật khẩu ở lần khởi động đầu;
  đổi sau đó sẽ làm hệ thống không kết nối được (cách sửa ở mục Xử lý sự cố).
- `.env` chứa token và mật khẩu, đã được loại khỏi Git — **không** đưa file này lên GitHub hay gửi cho người khác.

## Bước 6. Build và chạy

Đảm bảo Docker Desktop đang chạy, rồi:

```powershell
docker compose up -d --build
```

Lần đầu lệnh này tải và cài thư viện (10–30 phút, màn hình in rất nhiều dòng — bình thường). Khi xong sẽ thấy
các dòng `Container … Started`. Kiểm tra:

```powershell
docker compose ps
```

Kết quả mong đợi (cột STATUS):

```
SERVICE     STATUS
api         Up … (healthy)
frontend    Up … (healthy)
postgres    Up … (healthy)
seaweedfs   Up … (healthy)
worker      Up …
```

`frontend` có thể hiện `health: starting` trong khoảng 30 giây đầu. Kiểm tra API:

```powershell
curl.exe http://127.0.0.1:8001/api/health
```

Phải in `{"status":"ok"}`. (Trong PowerShell dùng `curl.exe`, không dùng `curl`.)

## Bước 7. Dùng thử lần đầu

1. Mở trình duyệt vào **http://127.0.0.1:8081**.
2. Kéo thả file `sample_data\sample_meeting.wav` (có sẵn trong thư mục dự án, dài 53 giây) vào ô tải lên.
3. Trạng thái chuyển *Đang chờ → Đang xử lý (tên bước) → Xong*. **Job đầu tiên mất thêm vài phút** vì worker
   tải model (~4 GB). Muốn xem chi tiết:

   ```powershell
   docker compose logs -f --tail=100 worker
   ```

   (bấm `Ctrl + C` để thoát xem log; hệ thống vẫn chạy). Log in lần lượt `Stage 1` … `Stage 7` rồi
   `Meeting … done`.
4. Bấm tên file để xem bản ghi: mỗi lượt nói có người nói, giới tính, cảm xúc; bấm một câu để nghe từ đó.

Tài liệu API (Swagger): http://127.0.0.1:8001/docs.

## Bước 8. Vận hành hằng ngày

| Việc | Lệnh |
|---|---|
| Tắt hệ thống (giữ dữ liệu) | `docker compose down` |
| Bật lại | `docker compose up -d` |
| Xem trạng thái | `docker compose ps` |
| Xem log xử lý | `docker compose logs -f --tail=100 worker` |
| Cập nhật lên bản mới | `git pull` rồi `docker compose up -d --build` |
| Xoá **toàn bộ** dữ liệu (cuộc họp, file, model đã tải) | `docker compose down -v` |

- Docker Desktop phải đang chạy thì hệ thống mới chạy. Nếu chưa tắt bằng `docker compose down`, các container tự
  bật lại mỗi khi Docker Desktop mở.
- Giao diện và API chỉ mở trên máy này (`127.0.0.1`), máy khác trong mạng không truy cập được.
- Dữ liệu nằm trong volume Docker (`bai2-meeting_pg_data`, `bai2-meeting_s3_data`, `bai2-meeting_model_cache`),
  không nằm trong thư mục dự án; xoá thư mục dự án không xoá dữ liệu.

## Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| `docker: command not found` / `error during connect` | Docker Desktop chưa cài hoặc chưa mở. Mở Docker Desktop, đợi *Engine running*. |
| `could not select device driver "nvidia"` hoặc lệnh kiểm tra GPU ở bước 2.3 lỗi | Driver NVIDIA cũ hoặc Docker chưa dùng WSL2. Cập nhật driver (2.1), `wsl --update`, bật WSL 2 engine (2.3), khởi động lại máy. |
| Job lỗi ở bước *Tách người nói* (`DiarizationError`, 401/403, `HF_TOKEN`) | Token sai hoặc chưa đồng ý đủ 3 model ở bước 3. Sửa `.env`, chạy `docker compose up -d --force-recreate api worker`, rồi bấm **Chạy lại** ở job lỗi. |
| `docker compose up` báo lỗi ở `init` (`dependency failed` / `exited (1)`), và `docker compose logs init` có `password authentication failed` | Đã đổi `POSTGRES_PASSWORD` sau lần chạy đầu. Đặt lại mật khẩu cũ trong `.env`; hoặc xoá dữ liệu và khởi tạo lại: `docker compose down -v` rồi `docker compose up -d`. |
| `ports are not available` hoặc `port is already allocated` (cổng 8001 / 8081) | Cổng đang bị chương trình khác dùng. Tắt chương trình đó, hoặc đổi số cổng bên trái trong mục `ports` của `api` / `frontend` ở `compose.yaml` (ví dụ `"127.0.0.1:9001:8000"`). |
| Build dừng giữa chừng vì mạng | Chạy lại `docker compose up -d --build`; các bước đã xong được giữ lại. |
| Hết dung lượng ổ đĩa khi build | Giải phóng ổ C (Docker Desktop lưu image trong ổ C), hoặc dọn image cũ: `docker system prune`. |
| Log worker có `CUDACachingAllocator … OOM` ở bước tách người nói | Cảnh báo của PyTorch trên card 4 GB; job vẫn xong bình thường. Chỉ cần xử lý khi job thật sự báo *Lỗi*. |
| Job đầu rất lâu, trạng thái đứng ở *Chuyển giọng nói thành chữ* | Đang tải model lần đầu; xem `docker compose logs -f worker`. |

Vẫn không được: chạy `docker compose logs --tail=200 api worker` và gửi kèm phần lỗi khi hỏi.

## Kết quả đo

Đo trên laptop RTX 3050 Ti 4 GB; cách đo và số liệu đầy đủ trong [`docs/benchmarks/`](docs/benchmarks/).

| Hạng mục | Kết quả |
|---|---|
| Chép lời (tỉ lệ sai chữ, 120 câu đọc FLEURS tiếng Việt) | 5.9 % |
| Nam / nữ (240 giọng FLEURS) | 239/240 đúng, 0 nhầm giới |
| Cảm xúc từ chữ (tập test UIT-VSMEC) | 68 % |
| Gắn nhầm cảm xúc trên giọng đọc bình thản | 5 % |
| Tốc độ | ~7 phút cho 1 giờ ghi âm |
| Bộ nhớ GPU | ổn định ~2 GB giữa các job |

## Kiến trúc

```
Trình duyệt ──► frontend (React, nginx :8081) ──/api──► api (FastAPI :8001)
                                                     │            │
                                               PostgreSQL     SeaweedFS (S3)
                                             (job, kết quả)   (file ghi âm gốc)
                                                     ▲
                                 worker (GPU, xử lý 1 file một lúc theo hàng đợi)
```

Worker xử lý mỗi file qua các bước: chuẩn hoá audio 16 kHz → chép lời (faster-whisper `large-v3-turbo`) →
tách người nói (pyannote) → gán người nói theo từng từ → gộp lượt nói → giới tính mỗi người (ECAPA-TDNN) →
cảm xúc mỗi lượt (giọng emotion2vec+ kết hợp chữ PhoBERT).

## Cấu hình

Các giá trị chỉnh trong `.env` (sau khi sửa, chạy `docker compose up -d --force-recreate api worker`):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HF_TOKEN` | — | Token Hugging Face (bắt buộc) |
| `MAX_UPLOAD_MB` | `500` | Dung lượng tối đa mỗi file tải lên |
| `GENDER_MALE_THRESHOLD` | `0.2` | Ngưỡng xác suất để kết luận giọng nam |
| `GENDER_MIN_CONFIDENCE` | `0.55` | Dưới mức này ghi giới tính "Không rõ" |
| `EMOTION_VOICE_WEIGHT` | `0.6` | Tỉ trọng giọng nói so với nội dung khi xét cảm xúc |
| `EMOTION_MIN_MARGIN` | `0.15` | Cảm xúc phải hơn "bình thường" bao nhiêu mới được gắn |

Danh sách đầy đủ: [`app/core/config.py`](app/core/config.py).

## Ghi nguồn

Hệ thống dùng các model: [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) (MIT),
[pyannote speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) (MIT) và
[community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) (CC BY 4.0),
[JaesungHuh/voice-gender-classifier](https://huggingface.co/JaesungHuh/voice-gender-classifier) (MIT),
[emotion2vec/emotion2vec_plus_large](https://huggingface.co/emotion2vec/emotion2vec_plus_large)
([FunASR Model License](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)),
[HalogenFlo/phobert-vsmec-emotion-recognition](https://huggingface.co/HalogenFlo/phobert-vsmec-emotion-recognition) (MIT).
File mẫu `sample_data/sample_meeting.wav` được tạo bằng [facebook/mms-tts-vie](https://huggingface.co/facebook/mms-tts-vie)
(CC BY-NC 4.0).
