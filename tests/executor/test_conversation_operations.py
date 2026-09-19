"""Tests for conversational deck structure and content operations in PPTXExecutor."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from autoslide.content.models import ContentBlock, ContentOrigin
from autoslide.executor.engine import PPTXExecutor
from autoslide.executor.errors import MutationRollbackError, TargetNotFoundError
from autoslide.ingest.models import BoundingBox
from autoslide.ingest.parser import PPTXIngestor
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import (
    AddContentOp,
    AddSlideOp,
    DeleteSlideOp,
    DuplicateSlideOp,
    ReorderSlideOp,
    TargetScope,
    TaskPlan,
)
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def test_add_slide_operation_at_end(tmp_path: Path):
    """Verify adding a blank/new slide at the end of the presentation."""
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_add_slide_end")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=2)],
        operations=[
            AddSlideOp(
                insert_at_index=2,
                content=[
                    ContentBlock(block_type="title", text="Newly Added Slide 2"),
                    ContentBlock(block_type="body", text="Detailed body points for new slide."),
                ],
            )
        ],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    assert result.working_path.exists()

    # Ingest resulting deck and verify postconditions
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 2
    assert len(inventory_after.slides) == 2
    # Check text on second slide
    slide2_texts = [sh.raw_text for sh in inventory_after.slides[1].shapes if sh.raw_text]
    assert any("Newly Added Slide 2" in t for t in slide2_texts)
    assert any("Detailed body points for new slide." in t for t in slide2_texts)


def test_add_slide_operation_at_beginning_with_provenance(tmp_path: Path):
    """Verify inserting a new slide at index 1 with AI_GENERATED origin metadata."""
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_add_slide_start")
    executor = PPTXExecutor()

    origin = ContentOrigin(kind="AI_GENERATED", runtime_name="gemini-3.7-flash")
    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[
            AddSlideOp(
                insert_at_index=1,
                content=[
                    ContentBlock(block_type="title", text="Executive Summary", origin=origin),
                ],
            )
        ],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 2
    # First slide should now be the new Executive Summary
    slide1_texts = [sh.raw_text for sh in inventory_after.slides[0].shapes if sh.raw_text]
    assert any("Executive Summary" in t for t in slide1_texts)


def test_add_slide_from_source_template(tmp_path: Path):
    """Verify adding a slide cloned from a source slide index."""
    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_add_slide_template")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        operations=[
            AddSlideOp(
                source_slide_index=2,
                insert_at_index=3,
                content=[
                    ContentBlock(block_type="title", text="Overview Clone"),
                ],
            )
        ],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)
    assert result.success is True

    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 4  # 3 original + 1 added


def test_delete_slide_operation(tmp_path: Path):
    """Verify deleting a slide reduces slide count and leaves a valid package."""
    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_del_slide")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=2)],
        operations=[DeleteSlideOp(slide_index=2)],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 2


def test_duplicate_slide_operation(tmp_path: Path):
    """Verify duplicating a slide creates a valid duplicate at target index."""
    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_dup_slide")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[DuplicateSlideOp(source_slide_index=1, insert_at_index=2)],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 4


def test_reorder_slide_operation(tmp_path: Path):
    """Verify moving a slide changes slide ordering."""
    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_reorder_slide")
    executor = PPTXExecutor()

    # Move slide 1 to index 3
    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[ReorderSlideOp(slide_index=1, new_index=3)],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    assert inventory_after.slide_count == 3
    # The original title slide (Slide 1) should now be Slide 3
    slide3_texts = [sh.raw_text for sh in inventory_after.slides[2].shapes if sh.raw_text]
    assert any("Executive Summary" in t for t in slide3_texts)


def test_add_content_operation(tmp_path: Path):
    """Verify adding arbitrary supported content block to a slide with bounds."""
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_add_content")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[
            AddContentOp(
                target_slide_index=1,
                content=ContentBlock(
                    block_type="text",
                    text="New Key Metrics:\n- Growth: +25%\n- Retention: 98%",
                ),
                bounds=BoundingBox(x=1500000, y=2500000, cx=9000000, cy=2000000),
            )
        ],
    )

    result = executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    assert result.success is True
    ingestor = PPTXIngestor()
    inventory_after, _ = ingestor.ingest(result.working_path, workspace)
    slide1_texts = [sh.raw_text for sh in inventory_after.slides[0].shapes if sh.raw_text]
    assert any("New Key Metrics" in t for t in slide1_texts)
    assert any("Growth: +25%" in t for t in slide1_texts)


def test_unsupported_content_rejection_and_rollback(tmp_path: Path):
    """Verify unsupported content types are rejected and trigger atomic rollback."""
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)
    initial_hash = hashlib.sha256(pptx_bytes).hexdigest()

    workspace = JobWorkspace.create(tmp_path, "job_unsupported_content")
    executor = PPTXExecutor()

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[
            AddContentOp(
                target_slide_index=1,
                content=ContentBlock(
                    block_type="unsupported_binary_payload",
                    text="MALFORMED_OR_UNSUPPORTED",
                ),
            )
        ],
    )

    with pytest.raises(MutationRollbackError, match="Unsupported content block type"):
        executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    # Immutability check on input file
    assert hashlib.sha256(input_file.read_bytes()).hexdigest() == initial_hash


def test_out_of_bounds_slide_operations_rollback(tmp_path: Path):
    """Verify out-of-bounds slide operations are caught and rolled back safely."""
    pptx_bytes = create_minimal_pptx()
    input_file = tmp_path / "original.pptx"
    input_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_oob_slide")
    executor = PPTXExecutor()

    # Attempt to delete non-existent slide 99
    plan = TaskPlan(
        schema_version="1.0",
        operations=[DeleteSlideOp(slide_index=99)],
    )

    with pytest.raises(MutationRollbackError, match="Slide index 99 out of bounds"):
        executor.execute(task_plan=plan, input_path=input_file, workspace=workspace)

    # Attempt to reorder non-existent slide 50
    plan_reorder = TaskPlan(
        schema_version="1.0",
        operations=[ReorderSlideOp(slide_index=50, new_index=1)],
    )

    with pytest.raises(MutationRollbackError, match="Slide index 50 out of bounds"):
        executor.execute(task_plan=plan_reorder, input_path=input_file, workspace=workspace)
