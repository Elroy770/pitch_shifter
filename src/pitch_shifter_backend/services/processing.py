from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException

from pitch_shifter_backend.core.config import get_settings
from pitch_shifter_backend.services.jobs import ArtifactFormat, job_store
from pitch_shifter_backend.services.storage import build_artifact_path


def _resolve_binary(path: Path, fallback_name: str) -> str:
    if path.exists():
        return str(path)
    discovered = shutil.which(fallback_name)
    if discovered:
        return discovered
    raise HTTPException(status_code=500, detail=f"{fallback_name} is not available")


def _run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _probe_media(source: Path, ffprobe_path: Path) -> dict[str, object]:
    command = [
        _resolve_binary(ffprobe_path, "ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(source),
    ]
    completed = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return json.loads(completed.stdout)


def _audio_streams(metadata: dict[str, object]) -> list[dict[str, object]]:
    streams = metadata.get("streams", [])
    return [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]


def _video_streams(metadata: dict[str, object]) -> list[dict[str, object]]:
    streams = metadata.get("streams", [])
    return [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]


def _has_video(metadata: dict[str, object]) -> bool:
    return bool(_video_streams(metadata))


def _sample_rate(metadata: dict[str, object]) -> int:
    for stream in _audio_streams(metadata):
        sample_rate = stream.get("sample_rate")
        if sample_rate:
            return int(sample_rate)
    return 44100


def _atempo_chain(tempo: float) -> str:
    filters: list[str] = []
    remaining = tempo
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    filters.append(f"atempo={remaining:.8f}")
    return ",".join(filters)


def _pitch_filter(sample_rate: int, semitones: float) -> str:
    factor = 2 ** (semitones / 12.0)
    tempo_correction = 1.0 / factor if factor else 1.0
    return f"asetrate={sample_rate * factor:.8f},{_atempo_chain(tempo_correction)},aresample={sample_rate}"


def _render_audio_variant(
    source: Path,
    destination: Path,
    semitones: float,
    ffmpeg_path: Path,
    ffprobe_path: Path,
) -> Path:
    metadata = _probe_media(source, ffprobe_path)
    if not _audio_streams(metadata):
        raise HTTPException(status_code=400, detail="Source media has no audio stream")

    sample_rate = _sample_rate(metadata)
    filter_chain = _pitch_filter(sample_rate, semitones)
    destination.parent.mkdir(parents=True, exist_ok=True)

    suffix = destination.suffix.lower().lstrip(".")
    command = [
        _resolve_binary(ffmpeg_path, "ffmpeg"),
        "-y",
        "-i",
        str(source),
        "-vn",
        "-filter:a",
        filter_chain,
    ]
    if suffix == "wav":
        command += ["-c:a", "pcm_s16le"]
    elif suffix == "mp3":
        command += ["-c:a", "libmp3lame", "-q:a", "2"]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported audio output format: {suffix}")
    command.append(str(destination))
    _run_command(command)
    return destination


def _render_video_variant(
    source: Path,
    destination: Path,
    semitones: float,
    ffmpeg_path: Path,
    ffprobe_path: Path,
) -> Path:
    metadata = _probe_media(source, ffprobe_path)
    if not _audio_streams(metadata):
        raise HTTPException(status_code=400, detail="Source media has no audio stream")

    sample_rate = _sample_rate(metadata)
    filter_chain = _pitch_filter(sample_rate, semitones)
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        _resolve_binary(ffmpeg_path, "ffmpeg"),
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        f"[0:a]{filter_chain}[aout]",
        "-map",
        "0:v:0?",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    _run_command(command)
    return destination


def _render_for_format(
    source: Path,
    destination: Path,
    semitones: float,
    ffmpeg_path: Path,
    ffprobe_path: Path,
) -> Path:
    metadata = _probe_media(source, ffprobe_path)
    if destination.suffix.lower() == ".mp4" and _has_video(metadata):
        return _render_video_variant(source, destination, semitones, ffmpeg_path, ffprobe_path)
    return _render_audio_variant(source, destination, semitones, ffmpeg_path, ffprobe_path)


async def process_job(job_id: str) -> None:
    settings = get_settings()
    job = job_store.get(job_id)
    if job is None:
        return

    job_store.update(job_id, status="running", error=None)
    try:
        if job.input_path is None:
            raise FileNotFoundError("Missing input path for job")

        source = Path(job.input_path)
        if not source.exists():
            raise FileNotFoundError(f"Input file not found: {source}")

        metadata = await asyncio.to_thread(_probe_media, source, settings.ffprobe_path)
        has_video = _has_video(metadata)
        if job.media_kind == "audio" and (job.output_format or "mp3") == "mp4":
            raise HTTPException(status_code=400, detail="Audio uploads cannot be exported as MP4")

        default_format: ArtifactFormat = "mp4" if has_video else "mp3"
        requested_format: ArtifactFormat = job.output_format or default_format

        artifact_formats: list[ArtifactFormat] = [requested_format]
        if has_video:
            artifact_formats.extend(["mp3", "wav"])
        else:
            artifact_formats.extend(["mp3", "wav"])

        artifacts: dict[str, str] = {}
        primary_output: str | None = None
        for artifact_format in dict.fromkeys(artifact_formats):
            destination = build_artifact_path(settings.jobs_dir / job_id, job_id, job.shift_semitones, artifact_format)
            result = await asyncio.to_thread(
                _render_for_format,
                source,
                destination,
                job.shift_semitones,
                settings.ffmpeg_path,
                settings.ffprobe_path,
            )
            artifacts[artifact_format] = str(result)
            if artifact_format == requested_format:
                primary_output = str(result)

        job_store.update(
            job_id,
            status="completed",
            output_path=primary_output,
            artifacts=artifacts,
        )
        # Keep only the latest 3 completed jobs and their artifacts.
        job_store.cleanup_old_jobs(keep_count=3)
    except Exception as exc:  # pragma: no cover - runtime safeguard
        job_store.update(job_id, status="failed", error=str(exc))


async def download_youtube(url: str, destination_dir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=500, detail="yt-dlp is not installed") from exc

    settings = get_settings()
    destination_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(destination_dir / "%(title).200s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "format": "bestvideo+bestaudio/best",
        "quiet": False,
        "no_warnings": False,
        "verbose": True,
        "remote_components": ["ejs:github"],
    }
    if settings.youtube_cookies_file is not None:
        cookies_file = settings.youtube_cookies_file
        if not cookies_file.exists():
            raise HTTPException(
                status_code=500,
                detail=f"YouTube cookies file not found: {cookies_file}",
            )
        import tempfile
        import shutil
        # yt-dlp tries to save cookies back, but k8s secrets are read-only.
        # Copy to a temporary location.
        tmp_cookies = Path(tempfile.gettempdir()) / "yt_cookies.txt"
        shutil.copy(cookies_file, tmp_cookies)
        options["cookiefile"] = str(tmp_cookies)

    def _download() -> Path:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return destination_dir / filename

    return await asyncio.to_thread(_download)
