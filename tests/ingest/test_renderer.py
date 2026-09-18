"""Tests for preview renderer and preview manifest generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from autoslide.ingest.errors import RenderError
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.renderer import (
    LibreOfficePreviewRenderer,
    MockPreviewRenderer,
)
from autoslide.jobs.workspace import JobWorkspace
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def test_mock_preview_renderer(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_001")
    renderer = MockPreviewRenderer()

    manifest = renderer.render_previews(pptx_file, workspace, slide_count=3)
    assert manifest.slide_count == 3
    assert len(manifest.previews) == 3
    assert manifest.renderer == "mock"

    manifest_file = workspace.root / "previews" / "manifest.json"
    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text())
    assert data["slide_count"] == 3

    for p in manifest.previews:
        preview_img = workspace.root / p.image_path
        assert preview_img.exists()
        assert preview_img.stat().st_size > 0


def test_ingestor_integration_with_renderer(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "single.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_002")
    ingestor = PPTXIngestor()
    inventory, manifest = ingestor.ingest(pptx_file, workspace)

    assert inventory.slide_count == 1
    assert manifest.slide_count == 1
    assert (workspace.root / "previews" / "manifest.json").exists()
    assert (workspace.root / "artifacts" / "inventory.json").exists()


def test_libreoffice_renderer_not_found(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_003")
    renderer = LibreOfficePreviewRenderer(soffice_bin="non_existent_soffice_binary_12345")

    with pytest.raises(RenderError, match="LibreOffice binary not found"):
        renderer.render_previews(pptx_file, workspace, slide_count=1)


def test_libreoffice_renderer_timeout(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_004")
    renderer = LibreOfficePreviewRenderer(timeout_seconds=0.001)

    with patch("shutil.which", return_value="/usr/bin/soffice"):
        with patch("subprocess.run", side_effect=TimeoutError("Timed out")):
            with pytest.raises(RenderError, match="timed out"):
                renderer.render_previews(pptx_file, workspace, slide_count=1)
