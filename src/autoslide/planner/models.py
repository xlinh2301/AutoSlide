"""Pydantic v2 data models for strongly-typed TaskPlan and allowlisted edit operations."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field

from autoslide.ingest.models import BoundingBox
from autoslide.planner.vocabulary import OperationType


class TargetReference(BaseModel):
    """Reference to a specific slide element or text range targeted for an edit."""

    slide_index: int
    object_ref: str | None = None
    run_range: list[int] | None = None


class TargetScope(BaseModel):
    """Boundary declaration for slides and shapes permissible to modify."""

    slide_index: int
    object_ref: str | None = None


from autoslide.content.models import ContentBlock


class BoundingBoxUpdate(BaseModel):
    """Spatial bounding box update dimensions in EMU."""

    x: int | None = None
    y: int | None = None
    cx: int | None = None
    cy: int | None = None


class BaseOperation(BaseModel):
    """Abstract base definition for all typed edit operations."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    preserve: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)


class ReplaceTextOp(BaseOperation):
    """Operation replacing text within a targeted shape, paragraph, or run."""

    op: Literal[OperationType.REPLACE_TEXT] = OperationType.REPLACE_TEXT
    target: TargetReference
    value: str


class FormatTextOp(BaseOperation):
    """Operation adjusting text formatting properties (size, weight, style, color)."""

    op: Literal[OperationType.FORMAT_TEXT] = OperationType.FORMAT_TEXT
    target: TargetReference
    font_name: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None


class ReplaceImageOp(BaseOperation):
    """Operation replacing an embedded picture or image placeholder."""

    op: Literal[OperationType.REPLACE_IMAGE] = OperationType.REPLACE_IMAGE
    target: TargetReference
    image_source: str


class MoveResizeShapeOp(BaseOperation):
    """Operation modifying the bounding box position or dimensions of a shape."""

    op: Literal[OperationType.MOVE_RESIZE_SHAPE] = OperationType.MOVE_RESIZE_SHAPE
    target: TargetReference
    bounds: BoundingBoxUpdate


class DuplicateSlideOp(BaseOperation):
    """Operation duplicating an existing slide."""

    op: Literal[OperationType.DUPLICATE_SLIDE] = OperationType.DUPLICATE_SLIDE
    source_slide_index: int
    insert_at_index: int | None = None


class DeleteSlideOp(BaseOperation):
    """Operation deleting a slide from the presentation."""

    op: Literal[OperationType.DELETE_SLIDE] = OperationType.DELETE_SLIDE
    slide_index: int


class AddSlideOp(BaseOperation):
    """Operation inserting a new slide with optional layout and initial content blocks."""

    op: Literal[OperationType.ADD_SLIDE] = OperationType.ADD_SLIDE
    source_slide_index: int | None = None
    insert_at_index: int = 1
    layout_ref: str | None = None
    content: list[ContentBlock] = Field(default_factory=list)


class ReorderSlideOp(BaseOperation):
    """Operation changing slide sequence order from slide_index to new_index."""

    op: Literal[OperationType.REORDER_SLIDE] = OperationType.REORDER_SLIDE
    slide_index: int
    new_index: int


class AddContentOp(BaseOperation):
    """Operation appending arbitrary supported content block to a slide."""

    op: Literal[OperationType.ADD_CONTENT] = OperationType.ADD_CONTENT
    target_slide_index: int
    content: ContentBlock
    bounds: BoundingBox | None = None


EditOperation = Annotated[
    Union[
        ReplaceTextOp,
        FormatTextOp,
        ReplaceImageOp,
        MoveResizeShapeOp,
        DuplicateSlideOp,
        DeleteSlideOp,
        AddSlideOp,
        ReorderSlideOp,
        AddContentOp,
    ],
    Field(discriminator="op"),
]


class TaskPlan(BaseModel):
    """Versioned schema contract representing planned edit actions and preservation invariants."""

    schema_version: Literal["1.0"] = "1.0"
    target_scope: list[TargetScope] = Field(default_factory=list)
    operations: list[EditOperation] = Field(default_factory=list)
    requires_review: bool = False
    rationale: str | None = None

    def to_card(self) -> dict[str, Any]:
        """Convert TaskPlan into a structured card representation for conversational turns."""
        return {
            "type": "plan",
            "schema_version": self.schema_version,
            "target_scope": [s.model_dump() for s in self.target_scope],
            "operations": [op.model_dump() for op in self.operations],
            "requires_review": self.requires_review,
            "rationale": self.rationale,
            "operation_count": len(self.operations),
        }

