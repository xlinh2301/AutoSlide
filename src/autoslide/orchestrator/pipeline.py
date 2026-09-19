"""Pipeline orchestrator linking Ingest, Planner, Executor, and Quality Gates."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any

from autoslide.events import EventLog
from autoslide.executor.engine import PPTXExecutor
from autoslide.executor.models import StructuralDiff
from autoslide.ingest.models import DeckInventory, ShapeInventoryItem, SlideInventoryItem
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.renderer import BasePreviewRenderer, MockPreviewRenderer
from autoslide.ingest.validator import validate_pptx_package
from autoslide.jobs.models import (
    DeckPreviewDiff,
    EditScope,
    JobState,
    OverlayBox,
    SlidePreviewDiff,
)
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import (
    OperationType,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from autoslide.planner.policy import PolicyGate
from autoslide.quality.models import (
    QualityReport,
    StructuralGateResult,
    VisualGateResult,
)
from autoslide.quality.repair import RepairLoopController
from autoslide.quality.structural import StructuralAcceptanceGate
from autoslide.quality.visual import VisualQualityGate


class JobOrchestrator:
    """Orchestrates end-to-end slide edit pipeline across all sub-modules."""

    def __init__(
        self,
        registry: JobRegistry,
        event_log: EventLog,
        renderer: BasePreviewRenderer | None = None,
    ):
        self.registry = registry
        self.event_log = event_log
        self.renderer = renderer or MockPreviewRenderer()
        self.ingestor = PPTXIngestor(default_renderer=self.renderer)
        self.policy_gate = PolicyGate(strict=True)
        self.executor = PPTXExecutor()
        self.structural_gate = StructuralAcceptanceGate(strict=False)
        self.visual_gate = VisualQualityGate()
        self.repair_controller = RepairLoopController(max_repair_attempts=3)

    def _find_target_shape(
        self,
        slide: SlideInventoryItem,
        instruction: str,
    ) -> ShapeInventoryItem | None:
        """Find the best matching shape for instruction on a given slide."""
        if not slide.shapes:
            return None

        lower_inst = instruction.lower()
        if any(k in lower_inst for k in ("title", "tiêu đề", "header", "heading")):
            for sh in slide.shapes:
                if sh.placeholder_type in ("title", "ctrTitle", "header", "subTitle") or any(
                    k in sh.shape_name.lower() for k in ("title", "header", "card header")
                ):
                    return sh
                if sh.children:
                    for child in sh.children:
                        if any(k in child.shape_name.lower() for k in ("title", "header", "card header")):
                            return child

        for sh in slide.shapes:
            if sh.raw_text:
                return sh
            if sh.children:
                for child in sh.children:
                    if child.raw_text:
                        return child

        return slide.shapes[0]

    def _resolve_plan(
        self,
        instruction: str,
        inventory: DeckInventory,
        scope: EditScope | None = None,
    ) -> TaskPlan:
        """Resolve natural language instruction, inventory, and optional scope into a concrete TaskPlan."""
        # Extract replacement text value from instruction
        new_value = instruction
        val_match = re.search(
            r'(?:tạo|thay|đổi|sửa|set|change|update)\s+(?:title|tiêu đề|subtitle|header)\s+(?:thành|sang|to|:\s*|cho\s+)?(?P<val>["\']?[^"\'\n]+?["\']?)(?:\s+(?:cho|ở|tại|on|in|for)\s+(?:slide|trang|slide\s*số)\s*#?\s*\d+|$)',
            instruction,
            re.IGNORECASE,
        )
        if val_match:
            extracted = val_match.group("val").strip(" \"'")
            if extracted:
                new_value = extracted

        target_scope = []
        operations = []

        # 1. Deck Scope (All Slides)
        if scope is not None and scope.kind == "deck":
            for slide in inventory.slides:
                t_shape = self._find_target_shape(slide, instruction)
                if t_shape:
                    target_scope.append(
                        TargetScope(
                            slide_index=slide.slide_index,
                            object_ref=t_shape.fingerprint,
                        )
                    )
                    operations.append(
                        ReplaceTextOp(
                            target=TargetReference(
                                slide_index=slide.slide_index,
                                object_ref=t_shape.fingerprint,
                            ),
                            value=new_value,
                            confidence=0.95,
                        )
                    )
            return TaskPlan(
                schema_version="1.0",
                target_scope=target_scope,
                operations=operations,
                requires_review=False,
            )

        # 2. Slide or Region Scope
        target_slide_idx = 1
        if scope is not None and scope.slide_index is not None:
            target_slide_idx = scope.slide_index
        else:
            slide_match = re.search(r"(?:slide|trang|slide\s*số)\s*#?\s*(\d+)", instruction, re.IGNORECASE)
            if slide_match:
                parsed_idx = int(slide_match.group(1))
                if any(s.slide_index == parsed_idx for s in inventory.slides):
                    target_slide_idx = parsed_idx

        target_slide = next((s for s in inventory.slides if s.slide_index == target_slide_idx), None)
        if target_slide is None and inventory.slides:
            target_slide = inventory.slides[0]

        target_shape = None

        if scope is not None and scope.kind == "region" and scope.region is not None:
            dim_cx = inventory.dimensions.cx or 12192000
            dim_cy = inventory.dimensions.cy or 6858000
            reg_x = int(scope.region.x * dim_cx)
            reg_y = int(scope.region.y * dim_cy)
            reg_cx = int(scope.region.width * dim_cx)
            reg_cy = int(scope.region.height * dim_cy)
            reg_x2 = reg_x + reg_cx
            reg_y2 = reg_y + reg_cy

            best_shape = None
            best_overlap = 0

            candidate_shapes = []
            if target_slide:
                for sh in target_slide.shapes:
                    candidate_shapes.append(sh)
                    if sh.children:
                        candidate_shapes.extend(sh.children)

            for sh in candidate_shapes:
                sh_x2 = sh.bounds.x + sh.bounds.cx
                sh_y2 = sh.bounds.y + sh.bounds.cy
                ix1 = max(reg_x, sh.bounds.x)
                iy1 = max(reg_y, sh.bounds.y)
                ix2 = min(reg_x2, sh_x2)
                iy2 = min(reg_y2, sh_y2)
                if ix1 < ix2 and iy1 < iy2:
                    overlap_area = (ix2 - ix1) * (iy2 - iy1)
                    score = overlap_area * (1.5 if sh.raw_text else 1.0)
                    if score > best_overlap:
                        best_overlap = score
                        best_shape = sh

            if best_shape is None:
                return TaskPlan(
                    schema_version="1.0",
                    target_scope=[TargetScope(slide_index=target_slide.slide_index if target_slide else 1)],
                    operations=[],
                    requires_review=True,
                    rationale=(
                        f"Ambiguous or unresolvable region scope on slide {target_slide_idx}: "
                        f"no resolvable elements found within region "
                        f"(x={scope.region.x:.2f}, y={scope.region.y:.2f}, w={scope.region.width:.2f}, h={scope.region.height:.2f})."
                    ),
                )
            target_shape = best_shape
        else:
            if target_slide:
                target_shape = self._find_target_shape(target_slide, instruction)

        if target_slide and target_shape:
            target_scope.append(
                TargetScope(
                    slide_index=target_slide.slide_index,
                    object_ref=target_shape.fingerprint,
                )
            )
            operations.append(
                ReplaceTextOp(
                    target=TargetReference(
                        slide_index=target_slide.slide_index,
                        object_ref=target_shape.fingerprint,
                    ),
                    value=new_value,
                    confidence=0.95,
                )
            )

        return TaskPlan(
            schema_version="1.0",
            target_scope=target_scope,
            operations=operations,
            requires_review=False,
        )

    def _build_preview_diff(
        self,
        job_id: str,
        workspace: JobWorkspace,
        slide_count: int,
        post_inventory: DeckInventory,
        structural_diff: StructuralDiff | None,
    ) -> DeckPreviewDiff:
        """Construct preview diff pairs with changed region highlights and save manifest artifact."""
        slide_diffs_map = {}
        if structural_diff and structural_diff.slide_diffs:
            for sd in structural_diff.slide_diffs:
                slide_diffs_map[sd.slide_index] = sd

        dim_cx = post_inventory.dimensions.cx or 12192000
        dim_cy = post_inventory.dimensions.cy or 6858000

        slide_preview_diffs: list[SlidePreviewDiff] = []
        for i in range(1, slide_count + 1):
            sd = slide_diffs_map.get(i)
            status = sd.status if sd else "unchanged"
            overlays: list[OverlayBox] = []
            changed_refs: list[str] = []

            if sd and sd.shape_diffs:
                target_slide_post = next((s for s in post_inventory.slides if s.slide_index == i), None)
                for sh_diff in sd.shape_diffs:
                    changed_refs.append(sh_diff.new_fingerprint)
                    matched_shape = None
                    if target_slide_post:
                        for sh in target_slide_post.shapes:
                            if sh.fingerprint == sh_diff.new_fingerprint:
                                matched_shape = sh
                                break
                            if sh.children:
                                for child in sh.children:
                                    if child.fingerprint == sh_diff.new_fingerprint:
                                        matched_shape = child
                                        break
                                if matched_shape:
                                    break
                    if matched_shape:
                        norm_x = max(0.0, min(1.0, matched_shape.bounds.x / dim_cx))
                        norm_y = max(0.0, min(1.0, matched_shape.bounds.y / dim_cy))
                        norm_w = max(0.0, min(1.0, matched_shape.bounds.cx / dim_cx))
                        norm_h = max(0.0, min(1.0, matched_shape.bounds.cy / dim_cy))
                        overlays.append(
                            OverlayBox(
                                x=norm_x,
                                y=norm_y,
                                width=norm_w,
                                height=norm_h,
                                shape_name=matched_shape.shape_name,
                                object_ref=matched_shape.fingerprint,
                                change_type="modified",
                            )
                        )

            slide_preview_diffs.append(
                SlidePreviewDiff(
                    slide_index=i,
                    before_image_url=f"/api/v1/jobs/{job_id}/artifacts/slide_{i:03d}_before.png",
                    after_image_url=f"/api/v1/jobs/{job_id}/artifacts/slide_{i:03d}_after.png",
                    status=status,
                    changed_object_refs=changed_refs,
                    overlays=overlays,
                )
            )

        changed_count = sum(1 for spd in slide_preview_diffs if spd.status == "modified")
        deck_diff = DeckPreviewDiff(
            job_id=job_id,
            total_slides=slide_count,
            changed_slides_count=changed_count,
            slides=slide_preview_diffs,
        )

        diff_file = workspace.artifacts_dir / "preview_diff.json"
        diff_file.write_text(deck_diff.model_dump_json(indent=2), encoding="utf-8")
        return deck_diff

    def run_pipeline(
        self,
        job_id: str,
        workspace: JobWorkspace,
        custom_plan: TaskPlan | None = None,
        scope: EditScope | None = None,
    ) -> QualityReport:
        """Run the end-to-end pipeline for the specified job."""
        job = self.registry.get(job_id)
        input_pptx = workspace.input_dir / "presentation.pptx"
        if not input_pptx.exists():
            pptx_files = list(workspace.input_dir.glob("*.pptx"))
            if not pptx_files:
                raise FileNotFoundError(f"No input PPTX found in {workspace.input_dir}")
            input_pptx = pptx_files[0]

        # 1. Ingestion Phase
        self.registry.transition(job_id, JobState.INGESTING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "INGESTING"})
        validate_pptx_package(input_pptx)
        initial_inventory = self.ingestor.parse(input_pptx)

        # Generate initial previews with "before" tag
        renderer = self.renderer
        renderer.render_previews(
            pptx_path=input_pptx,
            workspace=workspace,
            slide_count=initial_inventory.slide_count,
            prefix="before",
        )
        workspace.write_checkpoint("INGESTED", input_pptx)

        # 2. Planning Phase
        self.registry.transition(job_id, JobState.PLANNING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "PLANNING"})

        # Resolve or generate plan
        if custom_plan is not None:
            plan = custom_plan
        else:
            plan = self._resolve_plan(job.instruction, initial_inventory, scope=scope)

        # Save task_plan.json artifact
        task_plan_path = workspace.artifacts_dir / "task_plan.json"
        task_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

        # Check for unresolvable region scope / clarification needed
        if plan.requires_review:
            # Render "after" previews identical to before for display
            renderer.render_previews(
                pptx_path=input_pptx,
                workspace=workspace,
                slide_count=initial_inventory.slide_count,
                prefix="after",
            )
            self._build_preview_diff(
                job_id=job_id,
                workspace=workspace,
                slide_count=initial_inventory.slide_count,
                post_inventory=initial_inventory,
                structural_diff=None,
            )

            struct_result = StructuralGateResult(
                passed=True,
                verdict="PASSED",
                intended_count=0,
                unintended_violations=[],
            )
            visual_result = VisualGateResult(passed=True, findings=[], has_critical_or_error=False)
            report = QualityReport(
                overall_verdict="NEEDS_REVIEW",
                structural_result=struct_result,
                visual_result=visual_result,
                generated_at=datetime.now(timezone.utc).isoformat(),
                repair_attempts_count=0,
            )
            (workspace.artifacts_dir / "quality_report.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
            (workspace.artifacts_dir / "visual_findings.json").write_text("[]", encoding="utf-8")

            self.registry.transition(job_id, JobState.AWAITING_USER_APPROVAL)
            self.event_log.append(
                job_id,
                "NEEDS_CLARIFICATION",
                {"reason": plan.rationale},
            )
            self.event_log.append(
                job_id,
                "AWAITING_APPROVAL",
                {
                    "overall_verdict": "NEEDS_REVIEW",
                    "reason": plan.rationale,
                },
            )
            return report

        # Validate with PolicyGate
        policy_result = self.policy_gate.evaluate(plan, initial_inventory)
        if policy_result.verdict != "APPROVED":
            self.registry.transition(job_id, JobState.FAILED)
            self.event_log.append(
                job_id,
                "POLICY_REJECTED",
                {"violations": policy_result.violations},
            )
            raise ValueError(f"Plan rejected by policy gate: {'; '.join(policy_result.violations)}")

        # 3. Execution Phase
        self.registry.transition(job_id, JobState.EXECUTING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "EXECUTING"})
        exec_result = self.executor.execute(plan, input_pptx, workspace)

        # 4. Rendering Phase
        self.registry.transition(job_id, JobState.RENDERING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "RENDERING"})
        working_pptx = workspace.working_dir / "presentation.pptx"
        post_inventory = self.ingestor.parse(working_pptx)
        previews_after = renderer.render_previews(
            pptx_path=working_pptx,
            workspace=workspace,
            slide_count=post_inventory.slide_count,
            prefix="after",
        )

        # 5. Quality Verification Phase
        self.registry.transition(job_id, JobState.VERIFYING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "VERIFYING"})

        struct_result = self.structural_gate.evaluate(exec_result.structural_diff)
        visual_result = self.visual_gate.evaluate(post_inventory, previews_after)

        # Build preview diff model and artifact
        deck_diff = self._build_preview_diff(
            job_id=job_id,
            workspace=workspace,
            slide_count=max(initial_inventory.slide_count, post_inventory.slide_count),
            post_inventory=post_inventory,
            structural_diff=exec_result.structural_diff,
        )
        self.event_log.append(
            job_id,
            "PREVIEW_DIFF_GENERATED",
            deck_diff.model_dump(),
        )

        if exec_result.structural_diff:
            (workspace.artifacts_dir / "structural_diff.json").write_text(
                exec_result.structural_diff.model_dump_json(indent=2),
                encoding="utf-8",
            )

        repair_decision = self.repair_controller.decide(
            attempt=1,
            visual_findings=visual_result.findings,
            structural_result=struct_result,
        )

        overall_verdict = (
            "PASSED"
            if (struct_result.passed and visual_result.passed)
            else "NEEDS_REVIEW"
        )
        report = QualityReport(
            overall_verdict=overall_verdict,
            structural_result=struct_result,
            visual_result=visual_result,
            generated_at=datetime.now(timezone.utc).isoformat(),
            repair_attempts_count=0,
        )

        # Write quality report artifacts
        quality_report_path = workspace.artifacts_dir / "quality_report.json"
        quality_report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        visual_findings_path = workspace.artifacts_dir / "visual_findings.json"
        visual_findings_path.write_text(
            json.dumps([f.model_dump() for f in visual_result.findings], indent=2),
            encoding="utf-8",
        )

        # 6. Awaiting Human Review
        self.registry.transition(job_id, JobState.AWAITING_USER_APPROVAL)
        self.event_log.append(
            job_id,
            "AWAITING_APPROVAL",
            {
                "overall_verdict": overall_verdict,
                "repair_decision": repair_decision.action,
                "repair_reason": repair_decision.reason,
            },
        )

        return report

    def run_repair(
        self,
        job_id: str,
        workspace: JobWorkspace,
        feedback: str | None = None,
    ) -> QualityReport:
        """Rerun remediation, rendering, and verification asynchronously upon Repair decision."""
        input_pptx = workspace.input_dir / "presentation.pptx"
        if not input_pptx.exists():
            input_files = list(workspace.input_dir.glob("*.pptx"))
            if input_files:
                input_pptx = input_files[0]

        working_pptx = workspace.working_dir / "presentation.pptx"
        if not working_pptx.exists() and input_pptx.exists():
            shutil.copy(input_pptx, working_pptx)

        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "REPAIRING", "feedback": feedback})
        self.registry.force_state(job_id, JobState.REPAIRING)

        exec_diff = None
        if feedback:
            base_inv = self.ingestor.parse(input_pptx)
            repair_plan = self._resolve_plan(feedback, base_inv)
            if repair_plan.operations:
                self.registry.force_state(job_id, JobState.EXECUTING)
                self.event_log.append(job_id, "STAGE_STARTED", {"stage": "EXECUTING"})
                repair_exec_result = self.executor.execute(repair_plan, input_pptx, workspace)
                exec_diff = repair_exec_result.structural_diff

        workspace.write_checkpoint("REMEDIATED", working_pptx)

        # 2. Rendering Phase
        self.registry.force_state(job_id, JobState.RENDERING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "RENDERING"})
        renderer = self.renderer
        post_inventory = self.ingestor.parse(working_pptx)
        previews_after = renderer.render_previews(
            pptx_path=working_pptx,
            workspace=workspace,
            slide_count=post_inventory.slide_count,
            prefix="after",
        )

        # 3. Quality Verification Phase
        self.registry.force_state(job_id, JobState.VERIFYING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "VERIFYING"})

        struct_diff = exec_diff or StructuralDiff(
            slide_count_before=post_inventory.slide_count,
            slide_count_after=post_inventory.slide_count,
            intended_changes=[],
            unintended_changes=[],
        )
        struct_result = self.structural_gate.evaluate(struct_diff)
        visual_result = self.visual_gate.evaluate(post_inventory, previews_after)

        self._build_preview_diff(
            job_id=job_id,
            workspace=workspace,
            slide_count=post_inventory.slide_count,
            post_inventory=post_inventory,
            structural_diff=struct_diff,
        )

        repair_decision = self.repair_controller.decide(
            attempt=2,
            visual_findings=visual_result.findings,
            structural_result=struct_result,
        )

        overall_verdict = (
            "PASSED"
            if (struct_result.passed and visual_result.passed)
            else "NEEDS_REVIEW"
        )
        report = QualityReport(
            overall_verdict=overall_verdict,
            structural_result=struct_result,
            visual_result=visual_result,
            generated_at=datetime.now(timezone.utc).isoformat(),
            repair_attempts_count=1,
        )

        # Write updated artifacts
        quality_report_path = workspace.artifacts_dir / "quality_report.json"
        quality_report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        visual_findings_path = workspace.artifacts_dir / "visual_findings.json"
        visual_findings_path.write_text(
            json.dumps([f.model_dump() for f in visual_result.findings], indent=2),
            encoding="utf-8",
        )

        # 4. Return to Awaiting Approval
        self.registry.force_state(job_id, JobState.AWAITING_USER_APPROVAL)
        self.event_log.append(
            job_id,
            "AWAITING_APPROVAL",
            {
                "overall_verdict": overall_verdict,
                "repair_decision": repair_decision.action,
                "repair_reason": repair_decision.reason,
            },
        )

        return report
