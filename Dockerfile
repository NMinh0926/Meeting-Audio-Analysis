FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app
# ffmpeg: decoding for pydub and pyannote (torchcodec).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Separate layer: changing requirements must not re-download torch.
# CUDA 12 wheels also ship the cuBLAS/cuDNN libraries that faster-whisper (CTranslate2) needs.
RUN pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.14.0 torchaudio
# The PyPI torchcodec wheel targets CUDA 13; it must match torch's CUDA 12.6 build.
RUN pip install --index-url https://download.pytorch.org/whl/cu126 torchcodec==0.16.0
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib
COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt

COPY pytest.ini ./
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY sample_data ./sample_data

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/uploads /app/data/temp /app/.cache \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
