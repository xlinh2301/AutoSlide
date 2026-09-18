"""Fixtures for Phase 3 Edit Planner tests: golden plans, bad plans, and sample deck inventories."""

from __future__ import annotations

from autoslide.ingest.fingerprint import compute_shape_fingerprint
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
    TextRunInfo,
)


def create_sample_deck_inventory() -> DeckInventory:
    """Create a sample DeckInventory fixture with 2 slides and known object fingerprints."""
    b1 = BoundingBox(x=500000, y=500000, cx=8000000, cy=1000000)
    fp1 = compute_shape_fingerprint(1, "sp", "Title 1", "Executive Summary", b1, "title")

    b2 = BoundingBox(x=500000, y=1600000, cx=8000000, cy=800000)
    fp2 = compute_shape_fingerprint(1, "sp", "Subtitle 2", "Q3 Performance", b2, "subTitle")

    b3 = BoundingBox(x=1000000, y=1000000, cx=6000000, cy=3000000)
    fp3 = compute_shape_fingerprint(2, "tbl", "Financial Table", "Revenue $12.5M", b3)

    b4 = BoundingBox(x=7200000, y=1000000, cx=1500000, cy=1500000)
    fp4 = compute_shape_fingerprint(2, "pic", "Chart Icon", "", b4)

    s1 = SlideInventoryItem(
        slide_index=1,
        slide_id="256",
        r_id="rId1",
        slide_path="ppt/slides/slide1.xml",
        shapes=[
            ShapeInventoryItem(
                shape_id="2",
                shape_name="Title 1",
                shape_type="sp",
                placeholder_type="title",
                bounds=b1,
                z_order=0,
                text_runs=[TextRunInfo(text="Executive Summary", font_size=36.0, bold=True)],
                raw_text="Executive Summary",
                fingerprint=fp1,
            ),
            ShapeInventoryItem(
                shape_id="3",
                shape_name="Subtitle 2",
                shape_type="sp",
                placeholder_type="subTitle",
                bounds=b2,
                z_order=1,
                text_runs=[TextRunInfo(text="Q3 Performance", font_size=20.0, italic=True)],
                raw_text="Q3 Performance",
                fingerprint=fp2,
            ),
        ],
    )

    s2 = SlideInventoryItem(
        slide_index=2,
        slide_id="257",
        r_id="rId2",
        slide_path="ppt/slides/slide2.xml",
        shapes=[
            ShapeInventoryItem(
                shape_id="4",
                shape_name="Financial Table",
                shape_type="tbl",
                bounds=b3,
                z_order=0,
                text_runs=[],
                raw_text="Revenue $12.5M",
                fingerprint=fp3,
                table_data=[["Metric", "Value"], ["Revenue", "$12.5M"]],
            ),
            ShapeInventoryItem(
                shape_id="5",
                shape_name="Chart Icon",
                shape_type="pic",
                bounds=b4,
                z_order=1,
                text_runs=[],
                raw_text="",
                fingerprint=fp4,
            ),
        ],
    )

    return DeckInventory(
        slide_count=2,
        dimensions=SlideDimensions(cx=12192000, cy=6858000),
        slides=[s1, s2],
        created_at="2026-09-18T15:00:00Z",
        source_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )


def create_golden_replace_text_plan(inventory: DeckInventory) -> dict:
    fp = inventory.slides[0].shapes[0].fingerprint
    return {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 1, "object_ref": fp}],
        "operations": [
            {
                "op": "replace_text",
                "target": {"slide_index": 1, "object_ref": fp, "run_range": [0, 1]},
                "value": "Q4 Strategic Outlook",
                "preserve": ["font_family", "position", "theme_color"],
                "confidence": 0.98,
                "postconditions": ["text_equals_value", "no_unintended_objects_changed"],
            }
        ],
        "requires_review": False,
        "rationale": "Updated title to reflect Q4 Outlook as requested by user.",
    }


def create_golden_format_text_plan(inventory: DeckInventory) -> dict:
    fp = inventory.slides[0].shapes[1].fingerprint
    return {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 1, "object_ref": fp}],
        "operations": [
            {
                "op": "format_text",
                "target": {"slide_index": 1, "object_ref": fp},
                "font_size": 24.0,
                "bold": True,
                "color": "003366",
                "preserve": ["position"],
                "confidence": 0.95,
                "postconditions": ["font_size_matches", "bold_applied"],
            }
        ],
        "requires_review": False,
    }


def create_golden_replace_image_plan(inventory: DeckInventory) -> dict:
    fp = inventory.slides[1].shapes[1].fingerprint
    return {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 2, "object_ref": fp}],
        "operations": [
            {
                "op": "replace_image",
                "target": {"slide_index": 2, "object_ref": fp},
                "image_source": "assets/new_chart.png",
                "preserve": ["bounds", "aspect_ratio"],
                "confidence": 0.92,
                "postconditions": ["image_replaced", "bounds_preserved"],
            }
        ],
        "requires_review": False,
    }


def create_golden_move_resize_plan(inventory: DeckInventory) -> dict:
    fp = inventory.slides[0].shapes[0].fingerprint
    return {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 1, "object_ref": fp}],
        "operations": [
            {
                "op": "move_resize_shape",
                "target": {"slide_index": 1, "object_ref": fp},
                "bounds": {"x": 600000, "y": 600000, "cx": 8500000, "cy": 1200000},
                "preserve": ["text_content", "font_styling"],
                "confidence": 0.90,
                "postconditions": ["bounds_updated"],
            }
        ],
        "requires_review": False,
    }


def create_golden_duplicate_slide_plan() -> dict:
    return {
        "schema_version": "1.0",
        "target_scope": [{"slide_index": 2}],
        "operations": [
            {
                "op": "duplicate_slide",
                "source_slide_index": 2,
                "insert_at_index": 3,
                "preserve": ["slide_layout", "all_shapes"],
                "confidence": 0.99,
                "postconditions": ["slide_count_incremented"],
            }
        ],
        "requires_review": False,
    }
