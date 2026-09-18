"""Isolated filesystem workspace and checkpoint manager for jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

from autoslide.jobs.models import CheckpointRecord

STANDARD_DIRECTORIES: tuple[str, ...] = (
    "input",
    "working",
    "checkpoints",
    "previews",
    "artifacts",
    "logs",
)


class JobWorkspace:
    """Isolated directory structure and checkpoint storage for an individual job."""

    def __init__(self, root: Path, job_id: str):
        self.root = root
        self.job_id = job_id
        self._last_checkpoint_id: str | None = None
        self._checkpoint_seq = 0

    @classmethod
    def create(cls, root: Path, job_id: str) -> JobWorkspace:
        """Create and initialize an isolated workspace directory at <root>/jobs/<job_id>."""
        job_root = (root / "jobs" / job_id).resolve()
        job_root.mkdir(parents=True, exist_ok=True)

        for subdir_name in STANDARD_DIRECTORIES:
            (job_root / subdir_name).mkdir(parents=True, exist_ok=True)

        return cls(root=job_root, job_id=job_id)

    def path_for(self, name: str) -> Path:
        """Resolve a filename safely inside the workspace, preventing directory traversal."""
        resolved = (self.root / name).resolve()
        try:
            resolved.relative_to(self.root)
            return resolved
        except ValueError:
            # Traversal escape attempted: strip leading paths and place directly in workspace root
            safe_name = Path(name).name
            return self.root / safe_name

    def write_checkpoint(self, stage: str, source: Path) -> CheckpointRecord:
        """Hash and copy source file into the checkpoints directory, linking previous checkpoint."""
        if not source.exists():
            raise FileNotFoundError(f"Checkpoint source file not found: {source}")

        content = source.read_bytes()
        sha256_hash = hashlib.sha256(content).hexdigest()

        self._checkpoint_seq += 1
        checkpoint_id = f"cp_{self._checkpoint_seq:04d}_{uuid4().hex[:8]}"
        destination = (
            self.root / "checkpoints" / f"{stage.lower()}_{self._checkpoint_seq:03d}_{source.name}"
        )

        if destination.is_symlink():
            raise ValueError(f"Checkpoint destination cannot be a symlink: {destination}")

        destination.write_bytes(content)

        record = CheckpointRecord(
            checkpoint_id=checkpoint_id,
            job_id=self.job_id,
            stage=stage,
            path=destination,
            sha256=sha256_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_checkpoint_id=self._last_checkpoint_id,
        )
        self._last_checkpoint_id = checkpoint_id
        return record

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def working_dir(self) -> Path:
        return self.root / "working"

    @property
    def checkpoints_dir(self) -> Path:
        return self.root / "checkpoints"

    @property
    def previews_dir(self) -> Path:
        return self.root / "previews"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def last_checkpoint_id(self) -> str | None:
        """Return the ID of the most recent checkpoint written in this workspace."""
        return self._last_checkpoint_id
