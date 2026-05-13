FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OCR + binary deps cho pillow/pdf2image (CONTEXT mục Rủi ro 3)
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-vie \
      tesseract-ocr-eng \
      libpoppler-cpp-dev \
      poppler-utils \
      libjpeg-dev \
      zlib1g-dev \
      libgl1 \
      libglib2.0-0 \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

# CPU-only PyTorch (~150MB) thay vì default GPU build (~700MB + 13 nvidia-cuda packages = ~2.5GB)
# Tránh OOM Docker Desktop WSL2 khi flatten layer cuối (issue 2026-04-28).
RUN pip install --upgrade pip setuptools wheel \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu \
                   torch torchvision \
    && pip install .

# Volume mount điểm cache HuggingFace models (CONTEXT mục B)
VOLUME ["/root/.cache/docling"]

EXPOSE 8001

# Single uvicorn worker (Docling KHÔNG thread-safe, CONTEXT mục D)
CMD ["uvicorn", "docling_pipeline.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
