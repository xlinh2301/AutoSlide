"""Tests for TaskPlan schema models and discriminated edit operations."""

from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

from autoslide.planner.models import (
    DeleteSlideOp,
    DuplicateSlideOp,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceImageOp,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from autoslide.planner.vocabulary import OperationType, PreservationRuleType
from tests.fixtures.planner_samples import (
    create_golden_duplicate_slide_plan,
    create_golden_format_text_plan,
    create_golden_move_resize_plan,
    create_golden_replace_image_plan,
    create_golden_replace_text_plan,
    create_sample_deck_inventory,
)


def test_task_plan_deserialization_golden_replace_text():
    inv = create_sample_deck_inventory()
    raw = create_golden_replace_text_plan(inv)
    plan = TaskPlan.model_validate(raw)

    assert plan.schema_version == "1.0"
    assert len(plan.target_scope) == 1
    assert plan.target_scope[0].slide_index == 1
    assert len(plan.operations) == 1

    op = plan.operations[0]
    assert isinstance(op, ReplaceTextOp)
    assert op.op == OperationType.REPLACE_TEXT
    assert op.value == "Q4 Strategic Outlook"
    assert op.confidence == 0.98
    assert "font_family" in op.preserve


def test_task_plan_deserialization_golden_format_text():
    inv = create_sample_deck_inventory()
    raw = create_golden_format_text_plan(inv)
    plan = TaskPlan.model_validate(raw)

    op = plan.operations[0]
    assert isinstance(op, FormatTextOp)
    assert op.font_size == 24.0
    assert op.bold is True
    assert op.color == "003366"


def test_task_plan_deserialization_golden_replace_image():
    inv = create_sample_deck_inventory()
    raw = create_golden_replace_image_plan(inv)
    plan = TaskPlan.model_validate(raw)

    op = plan.operations[0]
    assert isinstance(op, ReplaceImageOp)
    assert op.image_source == "assets/new_chart.png"


def test_task_plan_deserialization_golden_move_resize():
    inv = create_sample_deck_inventory()
    raw = create_golden_move_resize_plan(inv)
    plan = TaskPlan.model_validate(raw)

    op = plan.operations[0]
    assert isinstance(op, MoveResizeShapeOp)
    assert op.bounds.x == 600000
    assert op.bounds.cx == 8500000


def test_task_plan_deserialization_golden_duplicate_slide():
    raw = create_golden_duplicate_slide_plan()
    plan = TaskPlan.model_validate(raw)

    op = plan.operations[0]
    assert isinstance(op, DuplicateSlideOp)
    assert op.source_slide_index == 2
    assert op.insert_at_index == 3


def test_task_plan_deserialization_delete_slide():
    raw = {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 2}],
        "operations": [
            {
                "op": "delete_slide",
                "slide_index": 2,
                "confidence": 0.95,
                "postconditions": ["slide_count_decremented"],
            }
        ],
    }
    plan = TaskPlan.model_validate(raw)
    op = plan.operations[0]
    assert isinstance(op, DeleteSlideOp)
    assert op.slide_index == 2


def test_task_plan_rejects_unknown_op():
    raw = {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 1}],
        "operations": [
            {
                "op": "run_arbitrary_script",
                "script": "import os; os.system('rm -rf /')",
                "confidence": 1.0,
            }
        ],
    }
    with pytest.raises(ValidationError):
        TaskPlan.model_validate(raw)


def test_task_plan_roundtrip_json():
    inv = create_sample_deck_inventory()
    raw = create_golden_replace_text_plan(inv)
    plan = TaskPlan.model_validate(raw)
    dumped = plan.model_dump_json()
    reloaded = TaskPlan.model_validate_json(dumped)
    assert reloaded == plan
