"""Tests for StructuralDiffEngine auditing intended and unintended changes."""

from __future__ import annotations

import pytest

from autoslide.executor.diff import StructuralDiffEngine
from autoslide.ingest.models import DeckInventory
from autoslide.planner.models import (
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from tests.fixtures.planner_samples import create_sample_deck_inventory


def test_structural_diff_intended_change():
    inv_before = create_sample_deck_inventory()
    # Create mutated inventory with updated slide 1 title
    inv_after = create_sample_deck_inventory()
    mut_shape = inv_after.slides[0].shapes[0]
    mut_shape.raw_text = "Updated Strategic Direction"
    mut_shape.fingerprint = "mutated_sha256_00000000000000000000000000000000000000000000000000"

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1, object_ref=inv_before.slides[0].shapes[0].fingerprint)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref=inv_before.slides[0].shapes[0].fingerprint),
                value="Updated Strategic Direction",
            )
        ],
    )

    engine = StructuralDiffEngine()
    diff = engine.compute_diff(inv_before, inv_after, plan)

    assert diff.slide_count_before == 2
    assert diff.slide_count_after == 2
    assert len(diff.intended_changes) == 1
    assert len(diff.unintended_changes) == 0
    assert diff.intended_changes[0].shape_name == "Title 1"
    assert diff.intended_changes[0].property_name == "text"


def test_structural_diff_detects_unintended_collateral_change():
    inv_before = create_sample_deck_inventory()
    inv_after = create_sample_deck_inventory()

    # Modify an object on slide 2 that was NOT in the plan
    mut_s2_shape = inv_after.slides[1].shapes[0]
    mut_s2_shape.raw_text = "Corrupted Text"
    mut_s2_shape.fingerprint = "corrupted_fp_1111111111111111111111111111111111111111111111111111"

    plan = TaskPlan(
        schema_version="1.0",
        target_scope=[TargetScope(slide_index=1)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref=inv_before.slides[0].shapes[0].fingerprint),
                value="New Title",
            )
        ],
    )

    engine = StructuralDiffEngine()
    diff = engine.compute_diff(inv_before, inv_after, plan)

    assert len(diff.unintended_changes) >= 1
    assert any(c.slide_index == 2 for c in diff.unintended_changes)
