"""Synthesise a short Vietnamese meeting with known speakers and text.

Uses the MMS Vietnamese TTS model (facebook/mms-tts-vie). Different "speakers" are made by
pitch/tempo shifting the same voice, which is enough for a pipeline smoke test and gives a
ground truth for transcription/diarization checks. Real recordings are still needed to judge
summary quality.

Run inside the container:
    docker compose run --rm -v "${PWD}:/app" api python -m scripts.make_sample_meeting
"""
import json
from pathlib import Path

import numpy as np
import torch
from pydub import AudioSegment
from transformers import AutoTokenizer, VitsModel

TTS_MODEL = "facebook/mms-tts-vie"
OUTPUT_DIR = Path("sample_data")
TARGET_RATE = 16_000
GAP_MS = 600

# Resampling factor per speaker: <1 lowers pitch and slows down, >1 raises it.
SPEAKERS = {"A": 1.0, "B": 0.8, "C": 1.2}

DIALOGUE = [
    ("A", "xin chào mọi người hôm nay chúng ta họp về kế hoạch ra mắt ứng dụng mới"),
    ("B", "bên kỹ thuật đã hoàn thành phần đăng nhập và thanh toán"),
    ("B", "còn chức năng thông báo thì cần thêm hai tuần nữa"),
    ("C", "bên marketing đề xuất ra mắt vào ngày mười lăm tháng mười một"),
    ("A", "vậy chúng ta chốt ngày ra mắt là mười lăm tháng mười một"),
    ("A", "anh bình phụ trách hoàn thành chức năng thông báo trước ngày ba mươi tháng mười"),
    ("B", "tôi đồng ý nhưng cần thêm một người kiểm thử"),
    ("C", "tôi sẽ chuẩn bị nội dung quảng cáo và gửi cho mọi người vào thứ sáu tuần này"),
    ("A", "vấn đề ngân sách quảng cáo chưa thống nhất chúng ta sẽ bàn lại vào tuần sau"),
    ("A", "cảm ơn mọi người buổi họp kết thúc tại đây"),
]


def synthesise(model, tokenizer, text: str) -> tuple[np.ndarray, int]:
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        waveform = model(**inputs).waveform[0].numpy()
    return waveform, model.config.sampling_rate


def to_segment(waveform: np.ndarray, rate: int, factor: float) -> AudioSegment:
    pcm = (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16)
    # Declaring a different frame rate shifts pitch and tempo together.
    shifted = AudioSegment(pcm.tobytes(), frame_rate=int(rate * factor), sample_width=2, channels=1)
    return shifted.set_frame_rate(TARGET_RATE)


def main() -> None:
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(TTS_MODEL)
    model = VitsModel.from_pretrained(TTS_MODEL)

    meeting = AudioSegment.silent(duration=500, frame_rate=TARGET_RATE)
    turns = []
    for speaker, text in DIALOGUE:
        waveform, rate = synthesise(model, tokenizer, text)
        segment = to_segment(waveform, rate, SPEAKERS[speaker])
        start = len(meeting) / 1000
        meeting += segment
        turns.append({"speaker": speaker, "start": round(start, 2),
                      "end": round(len(meeting) / 1000, 2), "text": text})
        meeting += AudioSegment.silent(duration=GAP_MS, frame_rate=TARGET_RATE)

    OUTPUT_DIR.mkdir(exist_ok=True)
    meeting.export(OUTPUT_DIR / "sample_meeting.wav", format="wav")
    (OUTPUT_DIR / "sample_meeting.json").write_text(
        json.dumps({"source": TTS_MODEL, "turns": turns}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(turns)} turns, {len(meeting) / 1000:.1f}s to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
