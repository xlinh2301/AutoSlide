"""Validation for Open Packaging Conventions (OPC) PPTX archives."""

from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from autoslide.ingest.errors import (
    CorruptPackageError,
    InvalidPackageError,
    UnsupportedPackageError,
)

CONTENT_TYPES_PART = "[Content_Types].xml"
ROOT_RELS_PART = "_rels/.rels"
DEFAULT_PRESENTATION_PART = "ppt/presentation.xml"


def validate_pptx_package(source: Path | bytes) -> zipfile.ZipFile:
    """Validate that the input is a valid, unencrypted OOXML presentation package.

    Returns the open ZipFile if valid, or raises an appropriate IngestError subclass.
    """
    if isinstance(source, Path):
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")
        if source.is_dir():
            raise InvalidPackageError(f"Expected file but got directory: {source}")
        try:
            zf = zipfile.ZipFile(source, "r")
        except (zipfile.BadZipFile, zipfile.LargeZipFile, Exception) as exc:
            raise CorruptPackageError(f"Corrupted or invalid zip archive: {exc}") from exc
    elif isinstance(source, (bytes, bytearray)):
        try:
            zf = zipfile.ZipFile(io.BytesIO(source), "r")
        except (zipfile.BadZipFile, zipfile.LargeZipFile, Exception) as exc:
            raise CorruptPackageError(f"Corrupted or invalid zip archive: {exc}") from exc
    else:
        raise TypeError(f"Expected Path or bytes, got {type(source)}")

    try:
        namelist = zf.namelist()

        # Check for encrypted packages
        if "EncryptedPackage" in namelist:
            zf.close()
            raise UnsupportedPackageError("Encrypted package is not supported")

        for info in zf.infolist():
            if info.flag_bits & 0x1:
                zf.close()
                raise UnsupportedPackageError("Encrypted package entry detected")

        # Check [Content_Types].xml
        if CONTENT_TYPES_PART not in namelist:
            zf.close()
            raise InvalidPackageError("Missing [Content_Types].xml")

        try:
            ct_content = zf.read(CONTENT_TYPES_PART)
            ET.fromstring(ct_content)
        except ET.ParseError as exc:
            zf.close()
            raise InvalidPackageError(f"Malformed [Content_Types].xml: {exc}") from exc

        # Check presentation part
        presentation_part = DEFAULT_PRESENTATION_PART
        if ROOT_RELS_PART in namelist:
            try:
                rels_content = zf.read(ROOT_RELS_PART)
                rels_root = ET.fromstring(rels_content)
                for rel in rels_root:
                    rel_type = rel.attrib.get("Type", "")
                    if rel_type.endswith("/officeDocument"):
                        target = rel.attrib.get("Target", "")
                        if target.startswith("/"):
                            presentation_part = target.lstrip("/")
                        else:
                            presentation_part = target
            except ET.ParseError:
                pass  # Fall back to default presentation part

        if presentation_part not in namelist:
            zf.close()
            raise InvalidPackageError(f"Missing presentation part: {presentation_part}")

        try:
            pres_content = zf.read(presentation_part)
            ET.fromstring(pres_content)
        except ET.ParseError as exc:
            zf.close()
            raise InvalidPackageError(f"Malformed presentation XML: {exc}") from exc

        return zf

    except Exception:
        zf.close()
        raise
