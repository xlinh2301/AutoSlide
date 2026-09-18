"""AutoSlide PPTX Executor Module."""

from autoslide.executor.diff import StructuralDiffEngine
from autoslide.executor.engine import PPTXExecutor
from autoslide.executor.errors import (
    ExecutorError,
    MutationRollbackError,
    TargetNotFoundError,
    UnintendedMutationError,
)
from autoslide.executor.models import (
    ExecutionResult,
    PropertyChange,
    ShapeDiff,
    SlideDiff,
    StructuralDiff,
)
from autoslide.executor.mutator import (
    apply_delete_slide,
    apply_duplicate_slide,
    apply_format_text,
    apply_move_resize,
    apply_replace_text,
)

__all__ = [
    "ExecutionResult",
    "ExecutorError",
    "MutationRollbackError",
    "PPTXExecutor",
    "PropertyChange",
    "ShapeDiff",
    "SlideDiff",
    "StructuralDiff",
    "StructuralDiffEngine",
    "TargetNotFoundError",
    "UnintendedMutationError",
    "apply_delete_slide",
    "apply_duplicate_slide",
    "apply_format_text",
    "apply_move_resize",
    "apply_replace_text",
]
