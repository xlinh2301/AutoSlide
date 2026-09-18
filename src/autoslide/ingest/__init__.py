"""AutoSlide PPTX Ingest Module."""

from autoslide.ingest.errors import (
    CorruptPackageError,
    IngestError,
    InvalidPackageError,
    RenderError,
    UnsupportedPackageError,
)
from autoslide.ingest.fingerprint import compute_shape_fingerprint
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    PreviewManifest,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
    SlidePreview,
    TextRunInfo,
)
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.renderer import (
    BasePreviewRenderer,
    LibreOfficePreviewRenderer,
    MockPreviewRenderer,
)
from autoslide.ingest.validator import validate_pptx_package

__all__ = [
    "BasePreviewRenderer",
    "BoundingBox",
    "CorruptPackageError",
    "DeckInventory",
    "IngestError",
    "InvalidPackageError",
    "LibreOfficePreviewRenderer",
    "MockPreviewRenderer",
    "PPTXIngestor",
    "PreviewManifest",
    "RenderError",
    "ShapeInventoryItem",
    "SlideDimensions",
    "SlideInventoryItem",
    "SlidePreview",
    "TextRunInfo",
    "UnsupportedPackageError",
    "compute_shape_fingerprint",
    "validate_pptx_package",
]
