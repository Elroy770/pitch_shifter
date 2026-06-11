from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
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
    def __init__(self, db_path: Path | str = "data/jobs.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    input_path TEXT,
                    output_path TEXT,
                    source_url TEXT,
                    original_name TEXT,
                    media_kind TEXT,
                    shift_semitones REAL,
                    output_format TEXT,
                    artifacts TEXT,
                    detected_key TEXT,
                    shifted_key TEXT,
                    error TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON jobs(created_at)")
            conn.commit()
            conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        artifacts = json.loads(row["artifacts"]) if row["artifacts"] else {}
        return JobRecord(
            id=row["id"],
            type=row["type"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            input_path=row["input_path"],
            output_path=row["output_path"],
            source_url=row["source_url"],
            original_name=row["original_name"],
            media_kind=row["media_kind"],
            shift_semitones=row["shift_semitones"],
            output_format=row["output_format"],
            artifacts=artifacts,
            detected_key=row["detected_key"],
            shifted_key=row["shifted_key"],
            error=row["error"],
        )

    def create(self, job_type: JobType, **kwargs: Any) -> JobRecord:
        job = JobRecord(id=str(uuid4()), type=job_type, **kwargs)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO jobs (
                    id, type, status, created_at, updated_at, input_path, output_path,
                    source_url, original_name, media_kind, shift_semitones, output_format,
                    artifacts, detected_key, shifted_key, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.type,
                    job.status,
                    job.created_at,
                    job.updated_at,
                    job.input_path,
                    job.output_path,
                    job.source_url,
                    job.original_name,
                    job.media_kind,
                    job.shift_semitones,
                    job.output_format,
                    json.dumps(job.artifacts),
                    job.detected_key,
                    job.shifted_key,
                    job.error,
                ),
            )
            conn.commit()
            conn.close()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if row is None:
                    return None
                return self._row_to_record(row)
            finally:
                conn.close()

    def update(self, job_id: str, **kwargs: Any) -> JobRecord:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if row is None:
                    raise ValueError(f"Job {job_id} not found")

                job = self._row_to_record(row)
                for key, value in kwargs.items():
                    setattr(job, key, value)
                job.updated_at = utc_now().isoformat()

                conn.execute(
                    """
                    UPDATE jobs SET type=?, status=?, created_at=?, updated_at=?, input_path=?,
                    output_path=?, source_url=?, original_name=?, media_kind=?, shift_semitones=?,
                    output_format=?, artifacts=?, detected_key=?, shifted_key=?, error=?
                    WHERE id=?
                    """,
                    (
                        job.type,
                        job.status,
                        job.created_at,
                        job.updated_at,
                        job.input_path,
                        job.output_path,
                        job.source_url,
                        job.original_name,
                        job.media_kind,
                        job.shift_semitones,
                        job.output_format,
                        json.dumps(job.artifacts),
                        job.detected_key,
                        job.shifted_key,
                        job.error,
                        job.id,
                    ),
                )
                conn.commit()
                return job
            finally:
                conn.close()

    def list_recent(self, limit: int = 10, status: str | None = None) -> list[JobRecord]:
        """List recent jobs, optionally filtered by status."""
        with self._lock:
            conn = self._get_conn()
            try:
                if status:
                    rows = conn.execute(
                        "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                        (status, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [self._row_to_record(row) for row in rows]
            finally:
                conn.close()

    def cleanup_old_jobs(self, keep_count: int = 3) -> None:
        """Delete old completed jobs, keeping only the most recent ones."""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT id FROM jobs
                    WHERE status = 'completed'
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (keep_count,),
                ).fetchall()
                keep_ids = {row["id"] for row in rows}

                rows = conn.execute(
                    "SELECT id, output_path FROM jobs WHERE status = 'completed'"
                ).fetchall()

                for row in rows:
                    job_id = row["id"]
                    if job_id in keep_ids:
                        continue

                    output_path = row["output_path"]
                    if output_path:
                        job_dir = Path(output_path).parent.parent
                        if job_dir.exists() and job_dir.is_dir():
                            shutil.rmtree(job_dir)

                    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

                conn.commit()
            finally:
                conn.close()


job_store = JobStore("data/jobs.db")


def job_root(settings: Any, job_id: str) -> Path:
    path = Path(settings.jobs_dir) / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path
