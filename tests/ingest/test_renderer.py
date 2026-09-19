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


def test_minimal_png_bytes_valid_with_pil():
    import io
    from PIL import Image
    from autoslide.ingest.renderer import MINIMAL_PNG_BYTES

    # Must open, verify, and load cleanly without UnidentifiedImageError or corrupt chunk error
    im = Image.open(io.BytesIO(MINIMAL_PNG_BYTES))
    assert im.format == "PNG"
    assert im.size == (1, 1)
    assert im.mode == "RGBA"
    im.verify()

    im_load = Image.open(io.BytesIO(MINIMAL_PNG_BYTES))
    im_load.load()
    assert im_load.getpixel((0, 0)) == (0, 0, 0, 0)


def test_mock_preview_images_are_valid_pngs(tmp_path: Path):
    import io
    from PIL import Image

    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_valid_png")
    renderer = MockPreviewRenderer()
    manifest = renderer.render_previews(pptx_file, workspace, slide_count=2, prefix="before")

    assert manifest.slide_count == 2
    for preview in manifest.previews:
        img_file = workspace.root / preview.image_path
        assert img_file.exists()
        opened = Image.open(img_file)
        assert opened.format == "PNG"
        assert opened.size == (1, 1)

    # Check prefixed files as well
    prefixed_file = workspace.root / "previews" / "slide_001_before.png"
    assert prefixed_file.exists()
    opened_prefix = Image.open(prefixed_file)
    assert opened_prefix.format == "PNG"


def test_libreoffice_renderer_fallback_to_mock_when_not_found(tmp_path: Path):
    from PIL import Image

    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_fallback_001")
    renderer = LibreOfficePreviewRenderer(
        soffice_bin="non_existent_binary_xyz",
        fallback_to_mock=True,
    )

    manifest = renderer.render_previews(pptx_file, workspace, slide_count=1)
    assert manifest.renderer == "mock"
    assert len(manifest.previews) == 1
    preview_path = workspace.root / manifest.previews[0].image_path
    assert preview_path.exists()
    img = Image.open(preview_path)
    assert img.format == "PNG"


def test_libreoffice_renderer_fallback_to_mock_on_timeout(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_render_fallback_002")
    renderer = LibreOfficePreviewRenderer(
        timeout_seconds=0.001,
        fallback_to_mock=True,
    )

    with patch("shutil.which", return_value="/usr/bin/soffice"):
        with patch("subprocess.run", side_effect=TimeoutError("Timed out")):
            manifest = renderer.render_previews(pptx_file, workspace, slide_count=1)
            assert manifest.renderer == "mock"
            assert len(manifest.previews) == 1


def test_select_preview_renderer():
    from autoslide.ingest.renderer import (
        LibreOfficePreviewRenderer,
        MockPreviewRenderer,
        select_preview_renderer,
    )

    # 1. When prefer_real is False, always return MockPreviewRenderer
    r_mock = select_preview_renderer(prefer_real=False)
    assert isinstance(r_mock, MockPreviewRenderer)

    # 2. When soffice is missing, return MockPreviewRenderer
    with patch("shutil.which", return_value=None):
        r_missing = select_preview_renderer(prefer_real=True)
        assert isinstance(r_missing, MockPreviewRenderer)

    # 3. When soffice and pdftoppm exist, return LibreOfficePreviewRenderer with fallback_to_mock
    def mock_which(cmd: str) -> str | None:
        if cmd in ("soffice", "pdftoppm"):
            return f"/usr/bin/{cmd}"
        return None

    with patch("shutil.which", side_effect=mock_which):
        r_lo = select_preview_renderer(prefer_real=True, fallback_to_mock=True)
        assert isinstance(r_lo, LibreOfficePreviewRenderer)
        assert r_lo.fallback_to_mock is True


def test_job_orchestrator_renderer_dependency_injection(tmp_path: Path):
    from autoslide.events import EventLog
    from autoslide.jobs.registry import JobRegistry
    from autoslide.orchestrator.pipeline import JobOrchestrator

    registry = JobRegistry(tmp_path / "jobs.db")
    event_log = EventLog(tmp_path / "logs")

    custom_renderer = MockPreviewRenderer()
    orchestrator = JobOrchestrator(
        registry=registry,
        event_log=event_log,
        renderer=custom_renderer,
    )
    assert orchestrator.renderer is custom_renderer
    assert orchestrator.ingestor.default_renderer is custom_renderer

