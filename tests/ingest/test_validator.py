"""Tests for PPTX OPC package validation."""

from __future__ import annotations

from pathlib import Path
import pytest

from autoslide.ingest.errors import (
    CorruptPackageError,
    InvalidPackageError,
    UnsupportedPackageError,
)
from autoslide.ingest.validator import validate_pptx_package
from tests.fixtures.pptx_samples import (
    create_corrupt_zip,
    create_encrypted_package,
    create_malformed_xml_pptx,
    create_minimal_pptx,
    create_missing_content_types_pptx,
)


def test_validate_valid_minimal_pptx(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "valid.pptx"
    pptx_file.write_bytes(pptx_bytes)

    zf = validate_pptx_package(pptx_file)
    assert zf is not None
    assert "[Content_Types].xml" in zf.namelist()
    zf.close()


def test_validate_valid_pptx_from_bytes():
    pptx_bytes = create_minimal_pptx()
    zf = validate_pptx_package(pptx_bytes)
    assert zf is not None
    zf.close()


def test_validate_corrupt_zip(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.pptx"
    corrupt_file.write_bytes(create_corrupt_zip())

    with pytest.raises(CorruptPackageError, match="Corrupted or invalid zip archive"):
        validate_pptx_package(corrupt_file)


def test_validate_missing_content_types(tmp_path: Path):
    bad_file = tmp_path / "missing_ct.pptx"
    bad_file.write_bytes(create_missing_content_types_pptx())

    with pytest.raises(InvalidPackageError, match="Missing \\[Content_Types\\]\\.xml"):
        validate_pptx_package(bad_file)


def test_validate_malformed_xml(tmp_path: Path):
    bad_xml_file = tmp_path / "malformed.pptx"
    bad_xml_file.write_bytes(create_malformed_xml_pptx())

    with pytest.raises(InvalidPackageError, match="Malformed presentation XML"):
        validate_pptx_package(bad_xml_file)


def test_validate_encrypted_package(tmp_path: Path):
    enc_file = tmp_path / "encrypted.pptx"
    enc_file.write_bytes(create_encrypted_package())

    with pytest.raises(UnsupportedPackageError, match="Encrypted package"):
        validate_pptx_package(enc_file)


def test_validate_nonexistent_file(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist.pptx"
    with pytest.raises(FileNotFoundError):
        validate_pptx_package(nonexistent)
