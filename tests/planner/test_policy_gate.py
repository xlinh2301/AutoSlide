"""Tests for PolicyGate: golden plans acceptance and rejection matrix enforcement."""

from __future__ import annotations

import pytest

from autoslide.planner.errors import (
    AmbiguousTargetError,
    LowConfidenceError,
    MalformedPlanError,
    PolicyViolationError,
    UnknownOperationError,
)
from autoslide.planner.models import TaskPlan
from autoslide.planner.policy import PolicyGate
from tests.fixtures.planner_samples import (
    create_golden_duplicate_slide_plan,
    create_golden_format_text_plan,
    create_golden_move_resize_plan,
    create_golden_replace_image_plan,
    create_golden_replace_text_plan,
    create_sample_deck_inventory,
)


def test_policy_gate_accepts_golden_plans():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate(min_confidence=0.80)

    plans = [
        create_golden_replace_text_plan(inventory),
        create_golden_format_text_plan(inventory),
        create_golden_replace_image_plan(inventory),
        create_golden_move_resize_plan(inventory),
        create_golden_duplicate_slide_plan(),
    ]

    for raw in plans:
        task_plan = TaskPlan.model_validate(raw)
        result = gate.evaluate(task_plan, inventory)
        assert result.verdict == "APPROVED"
        assert result.requires_review is False
        assert len(result.violations) == 0


def test_rejection_low_confidence_strict_mode():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate(min_confidence=0.80, strict=True)
    raw = create_golden_replace_text_plan(inventory)
    raw["operations"][0]["confidence"] = 0.65

    task_plan = TaskPlan.model_validate(raw)
    with pytest.raises(LowConfidenceError, match="Confidence 0.65 is below threshold 0.8"):
        gate.evaluate(task_plan, inventory)


def test_rejection_low_confidence_non_strict_marks_review():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate(min_confidence=0.80, strict=False)
    raw = create_golden_replace_text_plan(inventory)
    raw["operations"][0]["confidence"] = 0.70

    task_plan = TaskPlan.model_validate(raw)
    result = gate.evaluate(task_plan, inventory)
    assert result.verdict == "NEEDS_REVIEW"
    assert result.requires_review is True
    assert any("Confidence" in v for v in result.violations)


def test_rejection_ambiguous_nonexistent_target():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate(strict=True)
    raw = create_golden_replace_text_plan(inventory)
    # Target reference that does not exist in inventory
    fake_fp = "0000000000000000000000000000000000000000000000000000000000000000"
    raw["target_scope"] = [{"slide_index": 1, "object_ref": fake_fp}]
    raw["operations"][0]["target"]["object_ref"] = fake_fp

    task_plan = TaskPlan.model_validate(raw)
    with pytest.raises(AmbiguousTargetError, match="Target object_ref .* not found in inventory"):
        gate.evaluate(task_plan, inventory)


def test_rejection_operation_outside_declared_scope():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate(strict=True)
    raw = create_golden_replace_text_plan(inventory)
    # Scope declares slide 1, but op targets slide 2
    s2_fp = inventory.slides[1].shapes[0].fingerprint
    raw["operations"][0]["target"]["slide_index"] = 2
    raw["operations"][0]["target"]["object_ref"] = s2_fp

    task_plan = TaskPlan.model_validate(raw)
    with pytest.raises(PolicyViolationError, match="Operation target .* not covered by target_scope"):
        gate.evaluate(task_plan, inventory)


def test_rejection_arbitrary_code_injection_in_json():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate()

    raw = {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 1}],
        "operations": [
            {
                "op": "replace_text",
                "target": {"slide_index": 1, "object_ref": inventory.slides[0].shapes[0].fingerprint},
                "value": "__import__('os').system('cat /etc/passwd')",
                "confidence": 0.99,
            }
        ],
    }
    task_plan = TaskPlan.model_validate(raw)
    with pytest.raises(PolicyViolationError, match="Dangerous code injection pattern detected"):
        gate.evaluate(task_plan, inventory)


def test_parse_and_evaluate_raw_llm_json():
    inventory = create_sample_deck_inventory()
    gate = PolicyGate()

    raw_llm_output = f"""```json
{{
  "schema_version": "1.0",
  "target_scope": [{{"slide_index": 1, "object_ref": "{inventory.slides[0].shapes[0].fingerprint}"}}],
  "operations": [
    {{
      "op": "replace_text",
      "target": {{"slide_index": 1, "object_ref": "{inventory.slides[0].shapes[0].fingerprint}"}},
      "value": "2026 Strategy Roadmap",
      "confidence": 0.95
    }}
  ]
}}
```"""

    task_plan = gate.parse_plan_json(raw_llm_output)
    result = gate.evaluate(task_plan, inventory)
    assert result.verdict == "APPROVED"


def test_parse_plan_json_invalid_fails():
    gate = PolicyGate()
    bad_output = "I cannot fulfill this request, please edit manually."
    with pytest.raises(MalformedPlanError, match="Failed to parse JSON plan"):
        gate.parse_plan_json(bad_output)
