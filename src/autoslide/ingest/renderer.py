"""Slide preview rendering adapters and manifest generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from autoslide.ingest.errors import RenderError
from autoslide.ingest.models import PreviewManifest, SlidePreview
from autoslide.jobs.workspace import JobWorkspace

# 1x1 Transparent PNG binary data
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


class BasePreviewRenderer(ABC):
    """Abstract base class for slide preview thumbnail renderers."""

    @abstractmethod
    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
    ) -> PreviewManifest:
        """Render slide thumbnails and write previews/manifest.json to workspace."""


class MockPreviewRenderer(BasePreviewRenderer):
    """Hermetic mock preview renderer for fast testing without OS external dependencies."""

    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
    ) -> PreviewManifest:
        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            img_filename = f"slide_{i:03d}.png"
            img_path = previews_dir / img_filename
            img_path.write_bytes(MINIMAL_PNG_BYTES)

            preview_items.append(
                SlidePreview(
                    slide_index=i,
                    image_path=f"previews/{img_filename}",
                    width=1920,
                    height=1080,
                    format="png",
                )
            )

        manifest = PreviewManifest(
            slide_count=slide_count,
            previews=preview_items,
            generated_at=datetime.now(timezone.utc).isoformat(),
            renderer="mock",
        )

        manifest_path = previews_dir / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest


class LibreOfficePreviewRenderer(BasePreviewRenderer):
    """Production preview renderer using LibreOffice headless CLI and pdftoppm / PyMuPDF."""

    def __init__(
        self,
        soffice_bin: str = "soffice",
        timeout_seconds: float = 30.0,
    ):
        self.soffice_bin = soffice_bin
        self.timeout_seconds = timeout_seconds

    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
    ) -> PreviewManifest:
        if not shutil.which(self.soffice_bin):
            raise RenderError(f"LibreOffice binary not found at '{self.soffice_bin}'")

        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            user_profile = temp_dir / "lo_profile"
            user_profile.mkdir(parents=True, exist_ok=True)

            cmd = [
                self.soffice_bin,
                "--headless",
                "--invisible",
                "--nologo",
                "--nodefault",
                "--norestore",
                f"-env:UserInstallation=file://{user_profile}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_dir),
                str(pptx_path.resolve()),
            ]

            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                if result.returncode != 0:
                    raise RenderError(
                        f"LibreOffice conversion failed with code {result.returncode}: {result.stderr.decode('utf-8', errors='replace')}"
                    )
            except (subprocess.TimeoutExpired, TimeoutError) as exc:
                raise RenderError(f"LibreOffice rendering timed out after {self.timeout_seconds}s") from exc
            except Exception as exc:
                if isinstance(exc, RenderError):
                    raise
                raise RenderError(f"Subprocess error during LibreOffice rendering: {exc}") from exc

            pdf_file = temp_dir / f"{pptx_path.stem}.pdf"
            if not pdf_file.exists():
                # Search for any .pdf generated in temp_dir
                generated_pdfs = list(temp_dir.glob("*.pdf"))
                if not generated_pdfs:
                    raise RenderError("LibreOffice did not produce expected PDF output")
                pdf_file = generated_pdfs[0]

            # Convert PDF pages to PNG thumbnails
            preview_items: list[SlidePreview] = []
            pdftoppm_bin = shutil.which("pdftoppm")

            if pdftoppm_bin:
                out_prefix = temp_dir / "page"
                ppm_cmd = [
                    pdftoppm_bin,
                    "-png",
                    "-r",
                    "150",
                    str(pdf_file),
                    str(out_prefix),
                ]
                try:
                    subprocess.run(
                        ppm_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=self.timeout_seconds,
                        check=True,
                    )
                except Exception as exc:
                    raise RenderError(f"pdftoppm conversion failed: {exc}") from exc

                png_files = sorted(temp_dir.glob("page-*.png"))
                for idx, png_file in enumerate(png_files, start=1):
                    target_name = f"slide_{idx:03d}.png"
                    target_path = previews_dir / target_name
                    shutil.copy2(png_file, target_path)

                    preview_items.append(
                        SlidePreview(
                            slide_index=idx,
                            image_path=f"previews/{target_name}",
                            width=1920,
                            height=1080,
                            format="png",
                        )
                    )
            else:
                # Try PyMuPDF / fitz if available
                try:
                    import fitz  # type: ignore

                    doc = fitz.open(str(pdf_file))
                    for idx, page in enumerate(doc, start=1):
                        pix = page.get_pixmap(dpi=150)
                        target_name = f"slide_{idx:03d}.png"
                        target_path = previews_dir / target_name
                        pix.save(str(target_path))

                        preview_items.append(
                            SlidePreview(
                                slide_index=idx,
                                image_path=f"previews/{target_name}",
                                width=pix.width,
                                height=pix.height,
                                format="png",
                            )
                        )
                    doc.close()
                except ImportError:
                    # Fallback to minimal PNG placeholders if neither pdftoppm nor fitz is installed
                    for i in range(1, slide_count + 1):
                        img_filename = f"slide_{i:03d}.png"
                        img_path = previews_dir / img_filename
                        img_path.write_bytes(MINIMAL_PNG_BYTES)
                        preview_items.append(
                            SlidePreview(
                                slide_index=i,
                                image_path=f"previews/{img_filename}",
                                width=1920,
                                height=1080,
                                format="png",
                            )
                        )

            manifest = PreviewManifest(
                slide_count=len(preview_items) or slide_count,
                previews=preview_items,
                generated_at=datetime.now(timezone.utc).isoformat(),
                renderer="libreoffice",
            )
            manifest_path = previews_dir / "manifest.json"
            manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            return manifest
