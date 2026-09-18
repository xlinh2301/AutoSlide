"""Allowlisted edit operation vocabulary and preservation rule definitions."""

from __future__ import annotations

from enum import Enum


class OperationType(str, Enum):
    """Allowlisted operations supported by the AutoSlide planning and execution pipeline."""

    REPLACE_TEXT = "replace_text"
    FORMAT_TEXT = "format_text"
    REPLACE_IMAGE = "replace_image"
    MOVE_RESIZE_SHAPE = "move_resize_shape"
    DUPLICATE_SLIDE = "duplicate_slide"
    DELETE_SLIDE = "delete_slide"


class PreservationRuleType(str, Enum):
    """Standard preservation directives for unmutated properties."""

    FONT_FAMILY = "font_family"
    FONT_STYLING = "font_styling"
    POSITION = "position"
    BOUNDS = "bounds"
    ASPECT_RATIO = "aspect_ratio"
    THEME_COLOR = "theme_color"
    TEXT_CONTENT = "text_content"
    SLIDE_LAYOUT = "slide_layout"
    ALL_SHAPES = "all_shapes"
    UNTOUCHED_OBJECTS = "untouched_objects"


ALLOWLISTED_OPERATIONS = frozenset(op.value for op in OperationType)
