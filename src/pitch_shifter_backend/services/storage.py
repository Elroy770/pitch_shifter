from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str | None) -> str:
    raw = name or f"media-{uuid4().hex}"
    cleaned = SAFE_NAME_RE.sub("_", raw).strip("._")
    return cleaned or f"media-{uuid4().hex}"


async def save_upload(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
    await upload.close()
    return destination


def build_media_paths(base_dir: Path, original_name: str | None) -> tuple[Path, Path]:
    stem = safe_filename(original_name).rsplit(".", 1)[0]
    input_path = base_dir / "input" / safe_filename(original_name)
    output_path = base_dir / "output" / f"{stem}_processed.mp4"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return input_path, output_path


def build_artifact_path(base_dir: Path, job_id: str, semitones: float, output_format: str) -> Path:
    shift_label = f"{semitones:+g}".replace("+", "p").replace("-", "m")
    destination = base_dir / "output" / f"{job_id}_{shift_label}st.{output_format}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination
