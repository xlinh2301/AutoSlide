"""Tests for VisualQualityGate evaluating text overflow, shape clipping, and render failures."""

from __future__ import annotations

from pathlib import Path
import pytest

from autoslide.ingest.models import PreviewManifest, SlidePreview
from autoslide.quality.models import FindingCategory, FindingSeverity
from autoslide.quality.visual import VisualQualityGate
from tests.fixtures.quality_samples import create_overflow_inventory


def test_visual_gate_detects_overflow_and_clipping(tmp_path: Path):
    inventory = create_overflow_inventory()
    gate = VisualQualityGate()

    manifest = PreviewManifest(
        slide_count=1,
        previews=[SlidePreview(slide_index=1, image_path="previews/slide_001.png", width=1920, height=1080)],
        generated_at="2026-09-18T16:00:00Z",
        renderer="mock",
    )

    report = gate.evaluate(inventory=inventory, preview_manifest=manifest)

    assert len(report.findings) >= 2

    # Check text overflow finding
    overflow_f = next(
        (f for f in report.findings if f.category == FindingCategory.TEXT_OVERFLOW), None
    )
    assert overflow_f is not None
    assert overflow_f.severity in (FindingSeverity.ERROR, FindingSeverity.WARNING)
    assert overflow_f.shape_name == "Small Box"

    # Check bounds clipping finding
    clipping_f = next(
        (f for f in report.findings if f.category == FindingCategory.BOUNDS_CLIPPING), None
    )
    assert clipping_f is not None
    assert clipping_f.shape_name == "Offscreen Shape"


def test_visual_gate_clean_deck_passes():
    from tests.fixtures.planner_samples import create_sample_deck_inventory

    clean_inv = create_sample_deck_inventory()
    gate = VisualQualityGate()

    manifest = PreviewManifest(
        slide_count=2,
        previews=[
            SlidePreview(slide_index=1, image_path="previews/slide_001.png", width=1920, height=1080),
            SlidePreview(slide_index=2, image_path="previews/slide_002.png", width=1920, height=1080),
        ],
        generated_at="2026-09-18T16:00:00Z",
        renderer="mock",
    )

    report = gate.evaluate(inventory=clean_inv, preview_manifest=manifest)
    assert report.has_critical_or_error is False
