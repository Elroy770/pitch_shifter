FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies (ffmpeg, ffprobe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging metadata first so dependency and app installs can be cached.
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY frontend ./frontend

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "pitch_shifter_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
