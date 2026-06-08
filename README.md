# Pitch Shift

A local-first FastAPI backend plus a polished frontend for media ingest, real ffmpeg-based pitch shifting, and preview/download flows.

## What it includes

- Landing page with a clean hero section
- Upload form for MP3/MP4-style files
- YouTube URL ingest section
- Result panel with job summary, download state, and audio/video player placeholders
- Upload ingest for MP3/MP4 files
- YouTube URL ingest via `yt-dlp`
- In-memory job tracking with persistent files on disk
- Job status endpoint
- Download endpoint for processed artifacts
- Docker-friendly source layout

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn pitch_shifter_backend.main:app --reload --app-dir src
```

Then open http://127.0.0.1:8000/ for the frontend scaffold.

## Example requests

Upload:

```bash
curl -F "file=@sample.mp3" http://127.0.0.1:8000/ingest/upload
```

YouTube URL:

```bash
curl -X POST http://127.0.0.1:8000/ingest/youtube \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

Job status:

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
```

Download processed artifact:

```bash
curl -O -J http://127.0.0.1:8000/download/<job_id>
```

## Notes

The backend now performs real ffmpeg-based pitch shifting and can return MP3/WAV/MP4 artifacts depending on the input and requested format. The frontend stays lightweight and talks to the backend endpoints directly.
