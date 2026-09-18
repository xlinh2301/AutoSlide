"""Pipeline orchestrator linking Ingest, Planner, Executor, and Quality Gates."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from autoslide.events import EventLog
from autoslide.executor.engine import PPTXExecutor
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.renderer import MockPreviewRenderer
from autoslide.ingest.validator import validate_pptx_package
from autoslide.jobs.models import JobState
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
from autoslide.quality.models import QualityReport
from autoslide.quality.repair import RepairLoopController
from autoslide.quality.structural import StructuralAcceptanceGate
from autoslide.quality.visual import VisualQualityGate


from autoslide.executor.models import StructuralDiff
import re
import shutil
from autoslide.ingest.models import DeckInventory


class JobOrchestrator:
    """Orchestrates end-to-end slide edit pipeline across all sub-modules."""

    def __init__(
        self,
        registry: JobRegistry,
        event_log: EventLog,
    ):
        self.registry = registry
        self.event_log = event_log
        self.ingestor = PPTXIngestor()
        self.policy_gate = PolicyGate(strict=True)
        self.executor = PPTXExecutor()
        self.structural_gate = StructuralAcceptanceGate(strict=False)
        self.visual_gate = VisualQualityGate()
        self.repair_controller = RepairLoopController(max_repair_attempts=3)

    def _resolve_plan(
        self,
        instruction: str,
        inventory: DeckInventory,
    ) -> TaskPlan:
        """Resolve natural language instruction and inventory into a concrete TaskPlan."""
        # 1. Parse target slide index (1-based)
        target_slide_idx = 1
        slide_match = re.search(r"(?:slide|trang|slide\s*số)\s*#?\s*(\d+)", instruction, re.IGNORECASE)
        if slide_match:
            parsed_idx = int(slide_match.group(1))
            if any(s.slide_index == parsed_idx for s in inventory.slides):
                target_slide_idx = parsed_idx

        target_slide = next((s for s in inventory.slides if s.slide_index == target_slide_idx), None)
        if target_slide is None and inventory.slides:
            target_slide = inventory.slides[0]

        target_shape = None
        if target_slide and target_slide.shapes:
            lower_inst = instruction.lower()
            if any(k in lower_inst for k in ("title", "tiêu đề", "header", "heading")):
                for sh in target_slide.shapes:
                    if sh.placeholder_type in ("title", "ctrTitle", "header", "subTitle") or any(
                        k in sh.shape_name.lower() for k in ("title", "header", "card header")
                    ):
                        target_shape = sh
                        break
                    if sh.children:
                        for child in sh.children:
                            if any(k in child.shape_name.lower() for k in ("title", "header", "card header")):
                                target_shape = child
                                break
                        if target_shape:
                            break

            if target_shape is None:
                for sh in target_slide.shapes:
                    if sh.raw_text:
                        target_shape = sh
                        break
                    if sh.children:
                        for child in sh.children:
                            if child.raw_text:
                                target_shape = child
                                break
                        if target_shape:
                            break

            if target_shape is None:
                target_shape = target_slide.shapes[0]

        new_value = instruction
        val_match = re.search(
            r'(?:tạo|thay|đổi|sửa|set|change|update)\s+(?:title|tiêu đề|subtitle)\s+(?:thành|sang|to|:\s*|cho\s+)?(?P<val>["\']?[^"\'\n]+?["\']?)(?:\s+(?:cho|ở|tại|on|in|for)\s+(?:slide|trang|slide\s*số)\s*#?\s*\d+|$)',
            instruction,
            re.IGNORECASE,
        )
        if val_match:
            extracted = val_match.group("val").strip(" \"'")
            if extracted:
                new_value = extracted

        target_scope = []
        operations = []
        if target_slide and target_shape:
            target_scope.append(
                TargetScope(
                    slide_index=target_slide.slide_index,
                    object_ref=target_shape.fingerprint,
                )
            )
            operations.append(
                ReplaceTextOp(
                    target=TargetReference(slide_index=target_slide.slide_index, object_ref=target_shape.fingerprint),
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

    def run_pipeline(
        self,
        job_id: str,
        workspace: JobWorkspace,
        custom_plan: TaskPlan | None = None,
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

        # Generate initial previews
        renderer = MockPreviewRenderer()
        previews_before = renderer.render_previews(
            pptx_path=input_pptx,
            workspace=workspace,
            slide_count=initial_inventory.slide_count,
        )
        workspace.write_checkpoint("INGESTED", input_pptx)

        # 2. Planning Phase
        self.registry.transition(job_id, JobState.PLANNING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "PLANNING"})

        # Resolve or generate plan
        if custom_plan is not None:
            plan = custom_plan
        else:
            plan = self._resolve_plan(job.instruction, initial_inventory)

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

        # Save task_plan.json artifact
        task_plan_path = workspace.artifacts_dir / "task_plan.json"
        task_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

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
        )

        # 5. Quality Verification Phase
        self.registry.transition(job_id, JobState.VERIFYING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "VERIFYING"})

        struct_result = self.structural_gate.evaluate(exec_result.structural_diff)
        visual_result = self.visual_gate.evaluate(post_inventory, previews_after)

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

        if feedback:
            base_inv = self.ingestor.parse(input_pptx)
            repair_plan = self._resolve_plan(feedback, base_inv)
            if repair_plan.operations:
                self.registry.force_state(job_id, JobState.EXECUTING)
                self.event_log.append(job_id, "STAGE_STARTED", {"stage": "EXECUTING"})
                self.executor.execute(repair_plan, input_pptx, workspace)

        workspace.write_checkpoint("REMEDIATED", working_pptx)

        # 2. Rendering Phase
        self.registry.force_state(job_id, JobState.RENDERING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "RENDERING"})
        renderer = MockPreviewRenderer()
        post_inventory = self.ingestor.parse(working_pptx)
        previews_after = renderer.render_previews(
            pptx_path=working_pptx,
            workspace=workspace,
            slide_count=post_inventory.slide_count,
        )

        # 3. Quality Verification Phase
        self.registry.force_state(job_id, JobState.VERIFYING)
        self.event_log.append(job_id, "STAGE_STARTED", {"stage": "VERIFYING"})

        struct_diff = StructuralDiff(
            slide_count_before=post_inventory.slide_count,
            slide_count_after=post_inventory.slide_count,
            intended_changes=[],
            unintended_changes=[],
        )
        struct_result = self.structural_gate.evaluate(struct_diff)
        visual_result = self.visual_gate.evaluate(post_inventory, previews_after)

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
