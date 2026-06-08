from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

JobStatus = Literal["queued", "running", "completed", "failed"]
JobType = Literal["upload", "youtube"]
ArtifactFormat = Literal["mp3", "wav", "mp4"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobRecord:
    id: str
    type: JobType
    status: JobStatus = "queued"
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    updated_at: str = field(default_factory=lambda: utc_now().isoformat())
    input_path: str | None = None
    output_path: str | None = None
    source_url: str | None = None
    original_name: str | None = None
    media_kind: str | None = None
    shift_semitones: float = 0.0
    output_format: ArtifactFormat | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    detected_key: str | None = None
    shifted_key: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(self, job_type: JobType, **kwargs: Any) -> JobRecord:
        job = JobRecord(id=str(uuid4()), type=job_type, **kwargs)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = utc_now().isoformat()
            return job


job_store = JobStore()


def job_root(settings: Any, job_id: str) -> Path:
    path = Path(settings.jobs_dir) / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path
