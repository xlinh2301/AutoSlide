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
            # Look for any .pptx in input directory
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
            # Default single operation plan if target shape exists
            target_scope = []
            operations = []
            if initial_inventory.slides and initial_inventory.slides[0].shapes:
                target_shape = initial_inventory.slides[0].shapes[0]
                target_scope.append(
                    TargetScope(
                        slide_index=1,
                        object_ref=target_shape.fingerprint,
                    )
                )
                operations.append(
                    ReplaceTextOp(
                        target=TargetReference(slide_index=1, object_ref=target_shape.fingerprint),
                        value=job.instruction,
                        confidence=0.95,
                    )
                )

            plan = TaskPlan(
                schema_version="1.0",
                target_scope=target_scope,
                operations=operations,
                requires_review=False,
            )

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
