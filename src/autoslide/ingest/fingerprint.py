"""Composite deterministic object fingerprint generation for PPTX slide elements."""

from __future__ import annotations

import hashlib
from autoslide.ingest.models import BoundingBox


def compute_shape_fingerprint(
    slide_index: int,
    shape_type: str,
    shape_name: str,
    normalized_text: str,
    bounds: BoundingBox,
    placeholder_type: str | None = None,
) -> str:
    """Compute a deterministic, stable SHA-256 fingerprint for a slide shape.

    The fingerprint is invariant across serialization changes as it combines
    normalized semantic content, spatial geometry, shape type, and slide position.
    """
    norm_text = " ".join(normalized_text.split()).strip().lower()
    ph = placeholder_type.strip().lower() if placeholder_type else ""
    payload = (
        f"{slide_index}:{shape_type.strip().lower()}:{shape_name.strip()}:"
        f"{ph}:{norm_text}:{bounds.x}:{bounds.y}:{bounds.cx}:{bounds.cy}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
