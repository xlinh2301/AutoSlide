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


def create_boundary_subpixel_inventory() -> DeckInventory:
    """Create a DeckInventory with exact sub-pixel boundary conditions:
    1. Shape with +9 EMU right-edge overhang (simulating Weekly Report.pptx footer).
    2. Shape with +72,451 EMU bottom-edge margin (simulating Google Slides footer margin).
    3. Shape with exact +100,000 EMU tolerance threshold.
    4. Shape with +100,001 EMU exceeding tolerance (true clipping defect).
    5. Shape with -100,001 EMU left position (true clipping defect).
    """
    slide_w = 9144000
    slide_h = 5143500

    # 1. 9 EMU rounding error (x + cx = slide_w + 9)
    subpixel_shape = ShapeInventoryItem(
        shape_id="101",
        shape_name="Footer 9EMU Rounding",
        shape_type="sp",
        bounds=BoundingBox(x=8595309, y=4000000, cx=548700, cy=393600),  # x+cx = 9144009
        z_order=0,
        text_runs=[TextRunInfo(text="3", font_size=12.0)],
        raw_text="3",
        fingerprint="fp_subpixel_9emu",
    )

    # 2. 72,451 EMU rounding margin (y + cy = slide_h + 72451)
    bottom_margin_shape = ShapeInventoryItem(
        shape_id="102",
        shape_name="Footer Bottom Margin",
        shape_type="sp",
        bounds=BoundingBox(x=1000000, y=4822351, cx=548700, cy=393600),  # y+cy = 5215951 (+72451)
        z_order=1,
        text_runs=[TextRunInfo(text="Confidential", font_size=12.0)],
        raw_text="Confidential",
        fingerprint="fp_bottom_margin",
    )

    # 3. Exact tolerance boundary (+100,000 EMU)
    at_tolerance_shape = ShapeInventoryItem(
        shape_id="103",
        shape_name="At Tolerance Shape",
        shape_type="sp",
        bounds=BoundingBox(x=slide_w, y=1000000, cx=100000, cy=500000),  # x+cx = slide_w + 100000
        z_order=2,
        text_runs=[TextRunInfo(text="Boundary", font_size=14.0)],
        raw_text="Boundary",
        fingerprint="fp_at_tolerance",
    )

    # 4. Exceeding tolerance (+100,001 EMU)
    exceeding_shape = ShapeInventoryItem(
        shape_id="104",
        shape_name="True Exceeding Shape",
        shape_type="sp",
        bounds=BoundingBox(x=slide_w, y=2000000, cx=100001, cy=500000),  # x+cx = slide_w + 100001
        z_order=3,
        text_runs=[TextRunInfo(text="Clipped Right", font_size=14.0)],
        raw_text="Clipped Right",
        fingerprint="fp_exceeding_tolerance",
    )

    # 5. Negative offset exceeding tolerance (-100,001 EMU)
    negative_shape = ShapeInventoryItem(
        shape_id="105",
        shape_name="True Negative Offset Shape",
        shape_type="sp",
        bounds=BoundingBox(x=-100001, y=3000000, cx=500000, cy=500000),
        z_order=4,
        text_runs=[TextRunInfo(text="Clipped Left", font_size=14.0)],
        raw_text="Clipped Left",
        fingerprint="fp_negative_tolerance",
    )

    slide = SlideInventoryItem(
        slide_index=1,
        slide_id="256",
        r_id="rId1",
        slide_path="ppt/slides/slide1.xml",
        shapes=[subpixel_shape, bottom_margin_shape, at_tolerance_shape, exceeding_shape, negative_shape],
    )

    return DeckInventory(
        slide_count=1,
        dimensions=SlideDimensions(cx=slide_w, cy=slide_h),
        slides=[slide],
        created_at="2026-09-18T16:00:00Z",
        source_sha256="boundary_deck_hash_0000",
    )

