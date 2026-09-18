"""Fixtures for Phase 5 Quality Gates tests: structural diffs, overflow decks, and visual findings."""

from __future__ import annotations

from autoslide.executor.models import PropertyChange, StructuralDiff
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
    TextRunInfo,
)


def create_clean_structural_diff() -> StructuralDiff:
    """Create a clean StructuralDiff with only intended changes and 0 unintended changes."""
    return StructuralDiff(
        slide_count_before=2,
        slide_count_after=2,
        intended_changes=[
            PropertyChange(
                slide_index=1,
                shape_name="Title 1",
                object_ref="fp123",
                property_name="text",
                old_value="Old Title",
                new_value="New Intended Title",
            )
        ],
        unintended_changes=[],
    )


def create_dirty_structural_diff() -> StructuralDiff:
    """Create a StructuralDiff with collateral unintended changes."""
    return StructuralDiff(
        slide_count_before=2,
        slide_count_after=2,
        intended_changes=[
            PropertyChange(
                slide_index=1,
                shape_name="Title 1",
                object_ref="fp123",
                property_name="text",
                old_value="Old Title",
                new_value="New Intended Title",
            )
        ],
        unintended_changes=[
            PropertyChange(
                slide_index=2,
                shape_name="Financial Table",
                object_ref="fpTable456",
                property_name="text",
                old_value="Revenue $12.5M",
                new_value="Corrupted Value",
            )
        ],
    )


def create_overflow_inventory() -> DeckInventory:
    """Create a DeckInventory containing a shape with severe text overflow and bounds clipping."""
    # Text length 400 chars inside a tiny box 500x500 EMU
    long_text = "This is an excessively long text designed to trigger the text overflow heuristic in the visual quality gate. " * 4
    overflow_shape = ShapeInventoryItem(
        shape_id="10",
        shape_name="Small Box",
        shape_type="sp",
        bounds=BoundingBox(x=1000000, y=1000000, cx=2000000, cy=500000),  # Very narrow box
        z_order=0,
        text_runs=[TextRunInfo(text=long_text, font_size=36.0)],
        raw_text=long_text,
        fingerprint="fp_overflow_999",
    )

    # Shape placed beyond slide extents (12192000 x 6858000)
    clipped_shape = ShapeInventoryItem(
        shape_id="11",
        shape_name="Offscreen Shape",
        shape_type="sp",
        bounds=BoundingBox(x=11000000, y=6000000, cx=3000000, cy=2000000),  # x+cx = 14000000 > 12192000
        z_order=1,
        text_runs=[TextRunInfo(text="I am clipped", font_size=18.0)],
        raw_text="I am clipped",
        fingerprint="fp_clipped_888",
    )

    slide = SlideInventoryItem(
        slide_index=1,
        slide_id="256",
        r_id="rId1",
        slide_path="ppt/slides/slide1.xml",
        shapes=[overflow_shape, clipped_shape],
    )

    return DeckInventory(
        slide_count=1,
        dimensions=SlideDimensions(cx=12192000, cy=6858000),
        slides=[slide],
        created_at="2026-09-18T16:00:00Z",
        source_sha256="overflow_deck_hash_0000",
    )
