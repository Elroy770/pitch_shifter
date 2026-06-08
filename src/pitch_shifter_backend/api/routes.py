from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from pitch_shifter_backend.core.config import get_settings
from pitch_shifter_backend.services.jobs import job_root, job_store
from pitch_shifter_backend.services.processing import download_youtube, process_job
from pitch_shifter_backend.services.storage import safe_filename, save_upload

router = APIRouter()
settings = get_settings()
ALLOWED_UPLOAD_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm"}
ALLOWED_OUTPUT_FORMATS = {"mp3", "wav", "mp4"}


class IngestUrlRequest(BaseModel):
    url: HttpUrl
    shift_semitones: float = 0.0
    output_format: Optional[str] = None


def _media_kind_from_suffix(suffix: str) -> str:
    if suffix in {".mp3", ".m4a", ".wav", ".aac"}:
        return "audio"
    return "video"


def _normalize_output_format(requested_format: Optional[str]) -> Optional[str]:
    if requested_format is None:
        return None
    normalized = requested_format.strip().lower().lstrip(".")
    if normalized not in ALLOWED_OUTPUT_FORMATS:
        raise HTTPException(status_code=400, detail="output_format must be mp3, wav, or mp4")
    return normalized


def _job_response(job) -> dict[str, object]:
    payload = job.to_dict()
    payload["job_id"] = job.id
    return payload


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest/upload")
async def ingest_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shift_semitones: float = Form(0.0),
    output_format: Optional[str] = Form(None),
) -> dict[str, object]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Upload file must have a filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only MP3/MP4/WAV/WebM-style media uploads are supported")

    requested_output_format = _normalize_output_format(output_format)
    job = job_store.create(
        "upload",
        original_name=file.filename,
        media_kind=_media_kind_from_suffix(suffix),
        shift_semitones=shift_semitones,
        output_format=requested_output_format,
    )
    job_dir = job_root(settings, job.id)
    input_path = job_dir / "input" / safe_filename(file.filename)
    job_store.update(job.id, input_path=str(input_path))
    await save_upload(file, input_path)
    background_tasks.add_task(process_job, job.id)
    return _job_response(job)


@router.post("/ingest/youtube")
async def ingest_youtube(payload: IngestUrlRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    requested_output_format = _normalize_output_format(payload.output_format)
    job = job_store.create(
        "youtube",
        source_url=str(payload.url),
        media_kind="video",
        shift_semitones=payload.shift_semitones,
        output_format=requested_output_format,
    )
    job_dir = job_root(settings, job.id)

    async def _download_and_process() -> None:
        try:
            download_dir = job_dir / "input"
            downloaded = await download_youtube(str(payload.url), download_dir)
            job_store.update(job.id, input_path=str(downloaded))
            await process_job(job.id)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            job_store.update(job.id, status="failed", error=str(exc))

    background_tasks.add_task(_download_and_process)
    return _job_response(job)


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, object]:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = job.to_dict()
    if payload.get("status") == "completed":
        payload["download_url"] = f"/download/{job_id}"
        payload["download_urls"] = {fmt: f"/download/{job_id}?format={fmt}" for fmt in job.artifacts}
    payload["job_id"] = job.id
    return payload


@router.get("/download/{job_id}")
async def download(job_id: str, format: Optional[str] = None) -> FileResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.output_path:
        raise HTTPException(status_code=409, detail="Job output is not ready")

    output = job.output_path
    if format is not None:
        normalized = _normalize_output_format(format)
        if normalized is None:
            raise HTTPException(status_code=400, detail="format must be mp3, wav, or mp4")
        output = job.artifacts.get(normalized)
        if output is None:
            raise HTTPException(status_code=404, detail=f"No {normalized} artifact available for this job")
    return FileResponse(path=output, filename=Path(output).name)
