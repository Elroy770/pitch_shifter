from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pitch-shifter-backend"
    environment: str = "development"
    data_dir: Path = Path("data")
    uploads_dir: Path = Path("data/uploads")
    outputs_dir: Path = Path("data/outputs")
    jobs_dir: Path = Path("data/jobs")
    max_upload_mb: int = 500
    ffmpeg_path: Path = Path("ffmpeg")
    ffprobe_path: Path = Path("ffprobe")
    youtube_cookies_file: Path | None = None

    model_config = SettingsConfigDict(env_prefix="PITCH_", env_file=".env", extra="ignore")

    def resolve_paths(self) -> "Settings":
        self.data_dir = self.data_dir.expanduser().resolve()
        self.uploads_dir = self.uploads_dir.expanduser().resolve()
        self.outputs_dir = self.outputs_dir.expanduser().resolve()
        self.jobs_dir = self.jobs_dir.expanduser().resolve()
        self.ffmpeg_path = self.ffmpeg_path.expanduser()
        self.ffprobe_path = self.ffprobe_path.expanduser()
        if self.youtube_cookies_file is not None:
            self.youtube_cookies_file = self.youtube_cookies_file.expanduser()
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.resolve_paths()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    return settings
