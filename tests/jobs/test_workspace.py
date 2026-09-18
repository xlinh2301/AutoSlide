from pathlib import Path
import pytest

from autoslide.jobs.workspace import JobWorkspace


def test_workspace_contains_only_job_scoped_paths(tmp_path: Path):
    workspace = JobWorkspace.create(tmp_path, "job_123")
    assert workspace.root == tmp_path / "jobs" / "job_123"
    assert workspace.path_for("input.pptx").parent == workspace.root
    assert workspace.path_for("../outside.txt").parent == workspace.root


def test_checkpoint_records_sha256(tmp_path: Path):
    source = tmp_path / "working.pptx"
    source.write_bytes(b"pptx-fixture")
    workspace = JobWorkspace.create(tmp_path, "job_123")
    checkpoint = workspace.write_checkpoint("INGESTED", source)
    assert checkpoint.stage == "INGESTED"
    assert len(checkpoint.sha256) == 64
    assert checkpoint.path.exists()


def test_workspace_creates_standard_directories(tmp_path: Path):
    workspace = JobWorkspace.create(tmp_path, "job_456")
    expected_dirs = ["input", "working", "checkpoints", "previews", "artifacts", "logs"]
    for d in expected_dirs:
        assert (workspace.root / d).is_dir()


def test_checkpoint_parent_linkage(tmp_path: Path):
    source1 = tmp_path / "step1.pptx"
    source1.write_bytes(b"data-1")
    source2 = tmp_path / "step2.pptx"
    source2.write_bytes(b"data-2")

    workspace = JobWorkspace.create(tmp_path, "job_789")
    cp1 = workspace.write_checkpoint("INGESTED", source1)
    cp2 = workspace.write_checkpoint("PLANNED", source2)

    assert cp1.parent_checkpoint_id is None
    assert cp2.parent_checkpoint_id == cp1.checkpoint_id
