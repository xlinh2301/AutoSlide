"""Pydantic data models for PPTX inventory, objects, bounds, text runs, and preview manifests."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box geometry for a slide shape in EMU (English Metric Units)."""

    x: int = 0
    y: int = 0
    cx: int = 0
    cy: int = 0


class TextRunInfo(BaseModel):
    """Information for a single formatted text run."""

    text: str
    font_name: str | None = None
    font_size: float | None = None
    bold: bool = False
    italic: bool = False
    color: str | None = None


class ShapeInventoryItem(BaseModel):
    """Structured inventory data for a single shape, table, picture, or group on a slide."""

    shape_id: str
    shape_name: str
    shape_type: str
    placeholder_type: str | None = None
    bounds: BoundingBox
    z_order: int = 0
    text_runs: list[TextRunInfo] = Field(default_factory=list)
    raw_text: str = ""
    fingerprint: str
    table_data: list[list[str]] | None = None
    children: list[ShapeInventoryItem] | None = None


class SlideDimensions(BaseModel):
    """Dimensions of slides in the presentation deck in EMU."""

    cx: int = 12192000
    cy: int = 6858000


class SlideInventoryItem(BaseModel):
    """Structured inventory data for a single slide."""

    slide_index: int
    slide_id: str
    r_id: str
    slide_path: str
    shapes: list[ShapeInventoryItem] = Field(default_factory=list)
    layout_name: str | None = None


class DeckInventory(BaseModel):
    """Complete structured inventory for an ingested PPTX presentation deck."""

    slide_count: int
    dimensions: SlideDimensions
    slides: list[SlideInventoryItem] = Field(default_factory=list)
    created_at: str
    source_sha256: str


class SlidePreview(BaseModel):
    """Information regarding a rendered preview thumbnail for a single slide."""

    slide_index: int
    image_path: str
    width: int
    height: int
    format: str = "png"


class PreviewManifest(BaseModel):
    """Manifest tracking rendered slide preview thumbnails for a job."""

    slide_count: int
    previews: list[SlidePreview] = Field(default_factory=list)
    generated_at: str
    renderer: str
