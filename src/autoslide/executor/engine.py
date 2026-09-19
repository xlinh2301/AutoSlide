"""Deterministic PPTX Executor with atomic checkpointing, validation, and rollback safety."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import zipfile

from autoslide.executor.diff import StructuralDiffEngine
from autoslide.executor.errors import (
    ExecutorError,
    MutationRollbackError,
    TargetNotFoundError,
)
from autoslide.executor.models import ExecutionResult
from autoslide.executor.mutator import (
    apply_add_content,
    apply_add_slide,
    apply_delete_slide,
    apply_duplicate_slide,
    apply_format_text,
    apply_move_resize,
    apply_reorder_slide,
    apply_replace_text,
)
from autoslide.ingest.models import DeckInventory, ShapeInventoryItem
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.validator import validate_pptx_package
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import (
    AddContentOp,
    AddSlideOp,
    DeleteSlideOp,
    DuplicateSlideOp,
    FormatTextOp,
    MoveResizeShapeOp,
    ReorderSlideOp,
    ReplaceTextOp,
    TaskPlan,
)


class PPTXExecutor:
    """Orchestrates mutation execution, checkpointing, package integrity, and structural diffs."""

    def __init__(
        self,
        ingestor: PPTXIngestor | None = None,
        diff_engine: StructuralDiffEngine | None = None,
    ):
        self.ingestor = ingestor or PPTXIngestor()
        self.diff_engine = diff_engine or StructuralDiffEngine()

    def execute(
        self,
        task_plan: TaskPlan,
        input_path: Path,
        workspace: JobWorkspace,
    ) -> ExecutionResult:
        if not input_path.exists():
            raise FileNotFoundError(f"Input presentation file not found: {input_path}")

        # 1. Assert initial file immutability hash
        initial_bytes = input_path.read_bytes()
        initial_sha256 = hashlib.sha256(initial_bytes).hexdigest()

        # 2. Ingest baseline inventory
        inventory_before, _ = self.ingestor.ingest(input_path, workspace)

        # 3. Setup working copy
        working_dir = workspace.root / "working"
        working_dir.mkdir(parents=True, exist_ok=True)
        working_pptx = working_dir / "presentation.pptx"
        shutil.copy2(input_path, working_pptx)

        # Write initial checkpoint
        initial_cp = workspace.write_checkpoint("PRE_EXECUTION", working_pptx)
        last_valid_checkpoint_path = initial_cp.path
        checkpoints_count = 1

        # 4. Sequentially execute operations
        current_inventory = inventory_before

        # Build baseline fingerprint to shape identity map
        baseline_shape_map: dict[tuple[int, str], tuple[str, str]] = {}
        for s in inventory_before.slides:
            for sh in s.shapes:
                baseline_shape_map[(s.slide_index, sh.fingerprint)] = (sh.shape_id, sh.shape_name)
                if sh.shape_id:
                    baseline_shape_map[(s.slide_index, sh.shape_id)] = (sh.shape_id, sh.shape_name)
                if sh.children:
                    for child in sh.children:
                        baseline_shape_map[(s.slide_index, child.fingerprint)] = (child.shape_id, child.shape_name)
                        if child.shape_id:
                            baseline_shape_map[(s.slide_index, child.shape_id)] = (child.shape_id, child.shape_name)

        try:
            for idx, op in enumerate(task_plan.operations, start=1):
                # Read working files
                with zipfile.ZipFile(working_pptx, "r") as zf:
                    pkg_files = {name: zf.read(name) for name in zf.namelist()}

                # Match target shape if operation targets an element
                shape_info: ShapeInventoryItem | None = None
                if isinstance(op, (ReplaceTextOp, FormatTextOp, MoveResizeShapeOp)):
                    target_slide = op.target.slide_index
                    target_ref = op.target.object_ref

                    if target_ref is None:
                        raise TargetNotFoundError(
                            f"Target object_ref '{target_ref}' not found on slide {target_slide}"
                        )

                    if (target_slide, target_ref) in baseline_shape_map:
                        shape_id, shape_name = baseline_shape_map[(target_slide, target_ref)]
                    else:
                        shape_id, shape_name = target_ref, target_ref

                    # Search current inventory for matching shape_id, shape_name, or fingerprint
                    for s in current_inventory.slides:
                        if s.slide_index == target_slide:
                            for sh in s.shapes:
                                if (
                                    (shape_id and sh.shape_id == shape_id)
                                    or (shape_name and sh.shape_name == shape_name)
                                    or (target_ref and sh.fingerprint == target_ref)
                                ):
                                    shape_info = sh
                                    break
                                if sh.children:
                                    for child in sh.children:
                                        if (
                                            (shape_id and child.shape_id == shape_id)
                                            or (shape_name and child.shape_name == shape_name)
                                            or (target_ref and child.fingerprint == target_ref)
                                        ):
                                            shape_info = child
                                            break
                            if shape_info is not None:
                                break

                    if shape_info is None:
                        raise TargetNotFoundError(
                            f"Target object_ref '{target_ref}' (id: {shape_id}, name: {shape_name}) not found on slide {target_slide}"
                        )

                # Apply specific mutation
                if isinstance(op, ReplaceTextOp):
                    assert shape_info is not None
                    pkg_files = apply_replace_text(pkg_files, op, shape_info)
                elif isinstance(op, FormatTextOp):
                    assert shape_info is not None
                    pkg_files = apply_format_text(pkg_files, op, shape_info)
                elif isinstance(op, MoveResizeShapeOp):
                    assert shape_info is not None
                    pkg_files = apply_move_resize(pkg_files, op, shape_info)
                elif isinstance(op, DuplicateSlideOp):
                    if op.source_slide_index < 1 or op.source_slide_index > current_inventory.slide_count:
                        raise TargetNotFoundError(
                            f"Source slide index {op.source_slide_index} out of bounds (1..{current_inventory.slide_count})"
                        )
                    pkg_files = apply_duplicate_slide(
                        pkg_files,
                        source_slide_index=op.source_slide_index,
                        insert_at_index=op.insert_at_index,
                    )
                elif isinstance(op, DeleteSlideOp):
                    if op.slide_index < 1 or op.slide_index > current_inventory.slide_count:
                        raise TargetNotFoundError(
                            f"Slide index {op.slide_index} out of bounds (1..{current_inventory.slide_count})"
                        )
                    pkg_files = apply_delete_slide(pkg_files, slide_index=op.slide_index)
                elif isinstance(op, AddSlideOp):
                    if op.source_slide_index is not None and (
                        op.source_slide_index < 1 or op.source_slide_index > current_inventory.slide_count
                    ):
                        raise TargetNotFoundError(
                            f"Source slide index {op.source_slide_index} out of bounds (1..{current_inventory.slide_count})"
                        )
                    pkg_files = apply_add_slide(
                        pkg_files,
                        source_slide_index=op.source_slide_index,
                        insert_at_index=op.insert_at_index,
                        layout_ref=op.layout_ref,
                        content=op.content,
                    )
                elif isinstance(op, ReorderSlideOp):
                    if op.slide_index < 1 or op.slide_index > current_inventory.slide_count:
                        raise TargetNotFoundError(
                            f"Slide index {op.slide_index} out of bounds (1..{current_inventory.slide_count})"
                        )
                    pkg_files = apply_reorder_slide(
                        pkg_files,
                        slide_index=op.slide_index,
                        new_index=op.new_index,
                    )
                elif isinstance(op, AddContentOp):
                    if op.target_slide_index < 1 or op.target_slide_index > current_inventory.slide_count:
                        raise TargetNotFoundError(
                            f"Target slide index {op.target_slide_index} out of bounds (1..{current_inventory.slide_count})"
                        )
                    pkg_files = apply_add_content(
                        pkg_files,
                        target_slide_index=op.target_slide_index,
                        content=op.content,
                        bounds=op.bounds,
                    )
                else:
                    raise ExecutorError(f"Unsupported operation type: {type(op).__name__}")

                # Write mutated package to working copy
                with zipfile.ZipFile(working_pptx, "w") as out_zf:
                    for name, content in pkg_files.items():
                        out_zf.writestr(name, content)

                # Validate package integrity
                validate_pptx_package(working_pptx)

                # Record checkpoint
                cp_record = workspace.write_checkpoint(f"OP_{op.op.value.upper()}_{idx}", working_pptx)
                last_valid_checkpoint_path = cp_record.path
                checkpoints_count += 1

                # Re-parse working copy inventory for next step
                current_inventory, _ = self.ingestor.ingest(working_pptx, workspace)

        except Exception as exc:
            # Safe rollback to last valid checkpoint
            if last_valid_checkpoint_path and last_valid_checkpoint_path.exists():
                shutil.copy2(last_valid_checkpoint_path, working_pptx)
            raise MutationRollbackError(f"Execution failed and was rolled back: {exc}") from exc

        # 5. Final verification and structural diff
        inventory_after, _ = self.ingestor.ingest(working_pptx, workspace)
        structural_diff = self.diff_engine.compute_diff(
            inventory_before=inventory_before,
            inventory_after=inventory_after,
            plan=task_plan,
        )

        # Write structural_diff.json to workspace artifacts
        artifacts_dir = workspace.root / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        diff_path = artifacts_dir / "structural_diff.json"
        diff_path.write_text(structural_diff.model_dump_json(indent=2), encoding="utf-8")

        # 6. Verify original input immutability
        post_bytes = input_path.read_bytes()
        post_sha256 = hashlib.sha256(post_bytes).hexdigest()
        if post_sha256 != initial_sha256:
            raise RuntimeError(f"Original input file was modified during execution: {input_path}")

        return ExecutionResult(
            success=True,
            working_path=working_pptx,
            checkpoints_count=checkpoints_count,
            last_checkpoint_id=workspace.last_checkpoint_id,
            structural_diff=structural_diff,
        )
