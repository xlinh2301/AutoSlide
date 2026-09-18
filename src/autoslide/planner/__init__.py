"""AutoSlide Edit Planner Module."""

from autoslide.planner.builder import PromptPayloadBuilder
from autoslide.planner.errors import (
    AmbiguousTargetError,
    LowConfidenceError,
    MalformedPlanError,
    PlannerError,
    PolicyViolationError,
    UnknownOperationError,
)
from autoslide.planner.models import (
    BoundingBoxUpdate,
    DeleteSlideOp,
    DuplicateSlideOp,
    EditOperation,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceImageOp,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from autoslide.planner.policy import PolicyEvaluationResult, PolicyGate
from autoslide.planner.vocabulary import (
    ALLOWLISTED_OPERATIONS,
    OperationType,
    PreservationRuleType,
)

__all__ = [
    "ALLOWLISTED_OPERATIONS",
    "AmbiguousTargetError",
    "BoundingBoxUpdate",
    "DeleteSlideOp",
    "DuplicateSlideOp",
    "EditOperation",
    "FormatTextOp",
    "LowConfidenceError",
    "MalformedPlanError",
    "MoveResizeShapeOp",
    "OperationType",
    "PlannerError",
    "PolicyEvaluationResult",
    "PolicyGate",
    "PolicyViolationError",
    "PreservationRuleType",
    "PromptPayloadBuilder",
    "ReplaceImageOp",
    "ReplaceTextOp",
    "TargetReference",
    "TargetScope",
    "TaskPlan",
    "UnknownOperationError",
]
