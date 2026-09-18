"""Error definitions for the PPTX ingest module."""

from __future__ import annotations


class IngestError(Exception):
    """Base exception for all ingest errors."""


class CorruptPackageError(IngestError):
    """Raised when the package is not a valid zip archive or has corrupted entries."""


class InvalidPackageError(IngestError):
    """Raised when required OPC parts, content types, or presentation XML are missing or malformed."""


class UnsupportedPackageError(IngestError):
    """Raised when the package uses unsupported features, such as encryption or password protection."""


class RenderError(IngestError):
    """Raised when slide preview thumbnail generation fails."""
