"""Configuration settings for AutoSlide foundation runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_DATA_ROOT = Path("/tmp/autoslide")
DEFAULT_MAX_JOB_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_JOB_TIMEOUT_SECONDS = 300  # 5 minutes
VALID_RUNTIMES: tuple[str, ...] = ("codex", "gemini", "claude", "antigravity")


class Settings(BaseModel):
    """Immutable application settings loaded from environment or defaults."""

    model_config = ConfigDict(frozen=True)

    data_root: Path
    max_job_size_bytes: int = Field(default=DEFAULT_MAX_JOB_SIZE_BYTES, gt=0)
    job_timeout_seconds: int = Field(default=DEFAULT_JOB_TIMEOUT_SECONDS, gt=0)
    allowed_runtimes: tuple[str, ...] = VALID_RUNTIMES

    VALID_RUNTIMES: ClassVar[tuple[str, ...]] = VALID_RUNTIMES

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Create Settings reading strictly allowlisted environment variables."""
        env_map = os.environ if env is None else env

        raw_data_root = env_map.get("AUTOSLIDE_DATA_ROOT")
        if raw_data_root is not None:
            data_root = Path(raw_data_root)
            if not data_root.is_absolute():
                raise ValueError(f"AUTOSLIDE_DATA_ROOT must be an absolute path: '{raw_data_root}'")
        else:
            data_root = DEFAULT_DATA_ROOT

        raw_max_size = env_map.get("AUTOSLIDE_MAX_JOB_SIZE_BYTES")
        max_job_size_bytes = (
            int(raw_max_size) if raw_max_size is not None else DEFAULT_MAX_JOB_SIZE_BYTES
        )
        if max_job_size_bytes <= 0:
            raise ValueError("AUTOSLIDE_MAX_JOB_SIZE_BYTES must be positive")

        raw_timeout = env_map.get("AUTOSLIDE_JOB_TIMEOUT_SECONDS")
        job_timeout_seconds = (
            int(raw_timeout) if raw_timeout is not None else DEFAULT_JOB_TIMEOUT_SECONDS
        )
        if job_timeout_seconds <= 0:
            raise ValueError("AUTOSLIDE_JOB_TIMEOUT_SECONDS must be positive")

        raw_runtimes = env_map.get("AUTOSLIDE_ALLOWED_RUNTIMES")
        if raw_runtimes is not None:
            parsed_runtimes = tuple(
                part.strip() for part in raw_runtimes.split(",") if part.strip()
            )
            for runtime in parsed_runtimes:
                if runtime not in VALID_RUNTIMES:
                    raise ValueError(
                        f"Invalid runtime '{runtime}'. Allowed runtimes are {VALID_RUNTIMES}"
                    )
            allowed_runtimes = parsed_runtimes
        else:
            allowed_runtimes = VALID_RUNTIMES

        return cls(
            data_root=data_root,
            max_job_size_bytes=max_job_size_bytes,
            job_timeout_seconds=job_timeout_seconds,
            allowed_runtimes=allowed_runtimes,
        )

    def ensure_directories(self) -> None:
        """Bootstrap the data directory hierarchy."""
        (self.data_root / "jobs").mkdir(parents=True, exist_ok=True)
        (self.data_root / "artifacts").mkdir(parents=True, exist_ok=True)

    @property
    def jobs_dir(self) -> Path:
        return self.data_root / "jobs"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_root / "artifacts"
