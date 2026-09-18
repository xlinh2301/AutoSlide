"""Tests for PPTXExecutor lifecycle: execution, checkpointing, immutability, and safe rollback."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from autoslide.executor.engine import PPTXExecutor
from autoslide.executor.errors import MutationRollbackError
from autoslide.ingest.parser import PPTXIngestor
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import (
    BoundingBoxUpdate,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def test_executor_end_to_end_success(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)
    initial_hash = hashlib.sha256(pptx_bytes).hexdigest()

    workspace = JobWorkspace.create(tmp_path, "job_exec_001")
    ingestor = PPTXIngestor()
    inventory_before, _ = ingestor.ingest(input_file, workspace)

    title_shape = inventory_before.slides[0].shapes[0]
    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1, object_ref=title_shape.fingerprint)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref=title_shape.fingerprint),
                value="New Verified Deck Title",
            ),
            FormatTextOp(
                target=TargetReference(slide_index=1, object_ref=title_shape.fingerprint),
                font_size=32.0,
                bold=True,
                color="002244",
            ),
        ],
    )

    executor = PPTXExecutor()
    result = executor.execute(
        task_plan=plan,
        input_path=input_file,
        workspace=workspace,
    )

    assert result.success is True
    assert result.working_path.exists()
    assert result.checkpoints_count >= 1
    assert result.structural_diff is not None
    assert len(result.structural_diff.intended_changes) >= 1
    assert len(result.structural_diff.unintended_changes) == 0

    # Verify input file immutability
    post_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()
    assert initial_hash == post_hash

    # Verify structural diff artifact
    diff_file = workspace.root / "artifacts" / "structural_diff.json"
    assert diff_file.exists()


def test_executor_rollback_on_missing_target(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_exec_002")

    fake_fp = "non_existent_fp_0000000000000000000000000000000000000000000000000000"
    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1, object_ref=fake_fp)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref=fake_fp),
                value="Should fail and rollback",
            )
        ],
    )

    executor = PPTXExecutor()
    with pytest.raises(MutationRollbackError, match="Target object_ref .* not found on slide"):
        executor.execute(
            task_plan=plan,
            input_path=input_file,
            workspace=workspace,
        )

    # Confirm working copy exists in clean/rolled-back state
    working_file = workspace.root / "working" / "presentation.pptx"
    assert working_file.exists()
