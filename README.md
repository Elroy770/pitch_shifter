# Pitch Shifter Backend

Backend for a pitch-shifting web app that supports media uploads and YouTube ingest.

## Features

- Upload MP3/MP4/WAV/WebM media and shift pitch in semitones
- Paste a YouTube URL for karaoke songs or music videos up to 6 minutes
- Generate downloadable audio or video outputs
- Async job tracking for processing progress

## Development

This repository uses a `src/` layout and FastAPI backend code lives in `src/pitch_shifter_backend`.

## Runtime notes

- The backend keeps only the 3 most recent completed conversions and deletes older outputs automatically.
- To enable YouTube downloads that require authentication on Kubernetes, set `PITCH_YOUTUBE_COOKIES_FILE` to a mounted cookies file path.
