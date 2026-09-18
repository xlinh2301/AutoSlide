"""Tests for StructuralAcceptanceGate verifying intended vs unintended diffs."""

from __future__ import annotations

import pytest

from autoslide.quality.errors import StructuralRejectionError
from autoslide.quality.structural import StructuralAcceptanceGate
from tests.fixtures.quality_samples import (
    create_clean_structural_diff,
    create_dirty_structural_diff,
)


def test_structural_gate_passes_clean_diff():
    gate = StructuralAcceptanceGate()
    clean_diff = create_clean_structural_diff()
    result = gate.evaluate(clean_diff)

    assert result.passed is True
    assert result.verdict == "PASSED"
    assert len(result.unintended_violations) == 0


def test_structural_gate_rejects_unintended_changes():
    gate = StructuralAcceptanceGate(strict=False)
    dirty_diff = create_dirty_structural_diff()
    result = gate.evaluate(dirty_diff)

    assert result.passed is False
    assert result.verdict == "FAILED"
    assert len(result.unintended_violations) == 1
    assert "Financial Table" in result.unintended_violations[0]


def test_structural_gate_strict_raises_error():
    gate = StructuralAcceptanceGate(strict=True)
    dirty_diff = create_dirty_structural_diff()

    with pytest.raises(StructuralRejectionError, match="Unintended collateral modification"):
        gate.evaluate(dirty_diff)
