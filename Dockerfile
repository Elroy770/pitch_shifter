FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies (ffmpeg, curl, unzip for yt-dlp/deno)
RUN apt-get update && apt-get install -y ffmpeg curl unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY frontend ./frontend

# Update yt-dlp to ensure it works with the latest YouTube changes
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -U yt-dlp \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "pitch_shifter_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
