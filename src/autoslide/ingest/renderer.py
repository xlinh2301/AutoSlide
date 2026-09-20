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
from autoslide.ingest.models import (
    DeckSlideState,
    DeckStateResponse,
    PreviewManifest,
    SlidePreview,
)
from autoslide.jobs.workspace import JobWorkspace

# 1x1 Transparent PNG binary data (RFC 2083 standard, decodable by PIL and modern browsers)
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x60\x60\x60\x60"
    b"\x00\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB\x60\x82"
)


class BasePreviewRenderer(ABC):
    """Abstract base class for slide preview thumbnail renderers."""

    @abstractmethod
    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
        prefix: str = "",
    ) -> PreviewManifest:
        """Render slide thumbnails and write previews/manifest.json to workspace."""

    @abstractmethod
    def render_slide_delta(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        modified_indices: list[int],
        slide_count: int = 1,
    ) -> PreviewManifest:
        """Delta re-render specific modified slides in previews/after/."""


class MockPreviewRenderer(BasePreviewRenderer):
    """Hermetic mock preview renderer for fast testing without OS external dependencies."""

    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
        prefix: str = "",
    ) -> PreviewManifest:
        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        before_dir = workspace.before_previews_dir
        after_dir = workspace.after_previews_dir

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            img_path = previews_dir / base_filename
            img_path.write_bytes(MINIMAL_PNG_BYTES)

            # Write dual Before and After previews
            (before_dir / base_filename).write_bytes(MINIMAL_PNG_BYTES)
            (before_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
            (before_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)
            (after_dir / base_filename).write_bytes(MINIMAL_PNG_BYTES)
            (after_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
            (after_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)

            if prefix:
                prefixed_filename = f"slide_{i:03d}_{prefix}.png"
                (previews_dir / prefixed_filename).write_bytes(MINIMAL_PNG_BYTES)

            preview_items.append(
                SlidePreview(
                    slide_index=i,
                    image_path=f"previews/{base_filename}",
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

    def render_slide_delta(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        modified_indices: list[int],
        slide_count: int = 1,
    ) -> PreviewManifest:
        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        after_dir = workspace.after_previews_dir

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            if not modified_indices or i in modified_indices:
                img_path = previews_dir / base_filename
                img_path.write_bytes(MINIMAL_PNG_BYTES)
                (after_dir / base_filename).write_bytes(MINIMAL_PNG_BYTES)
                (after_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
                (after_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)

            preview_items.append(
                SlidePreview(
                    slide_index=i,
                    image_path=f"previews/{base_filename}",
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
        fallback_to_mock: bool = False,
    ):
        self.soffice_bin = soffice_bin
        self.timeout_seconds = timeout_seconds
        self.fallback_to_mock = fallback_to_mock

    def render_previews(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
        prefix: str = "",
    ) -> PreviewManifest:
        if not shutil.which(self.soffice_bin):
            if self.fallback_to_mock:
                return MockPreviewRenderer().render_previews(
                    pptx_path=pptx_path,
                    workspace=workspace,
                    slide_count=slide_count,
                    prefix=prefix,
                )
            raise RenderError(f"LibreOffice binary not found at '{self.soffice_bin}'")

        try:
            return self._render_libreoffice(
                pptx_path=pptx_path,
                workspace=workspace,
                slide_count=slide_count,
                prefix=prefix,
            )
        except RenderError:
            if self.fallback_to_mock:
                return MockPreviewRenderer().render_previews(
                    pptx_path=pptx_path,
                    workspace=workspace,
                    slide_count=slide_count,
                    prefix=prefix,
                )
            raise

    def render_slide_delta(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        modified_indices: list[int],
        slide_count: int = 1,
    ) -> PreviewManifest:
        if not shutil.which(self.soffice_bin):
            if self.fallback_to_mock:
                return MockPreviewRenderer().render_slide_delta(
                    pptx_path=pptx_path,
                    workspace=workspace,
                    modified_indices=modified_indices,
                    slide_count=slide_count,
                )
            raise RenderError(f"LibreOffice binary not found at '{self.soffice_bin}'")

        try:
            return self._render_libreoffice_delta(
                pptx_path=pptx_path,
                workspace=workspace,
                modified_indices=modified_indices,
                slide_count=slide_count,
            )
        except RenderError:
            if self.fallback_to_mock:
                return MockPreviewRenderer().render_slide_delta(
                    pptx_path=pptx_path,
                    workspace=workspace,
                    modified_indices=modified_indices,
                    slide_count=slide_count,
                )
            raise

    def _render_libreoffice(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        slide_count: int = 1,
        prefix: str = "",
    ) -> PreviewManifest:
        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        before_dir = workspace.before_previews_dir
        after_dir = workspace.after_previews_dir

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
                generated_pdfs = list(temp_dir.glob("*.pdf"))
                if not generated_pdfs:
                    raise RenderError("LibreOffice did not produce expected PDF output")
                pdf_file = generated_pdfs[0]

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

                    # Copy to before and after preview dirs
                    shutil.copy2(png_file, before_dir / target_name)
                    shutil.copy2(png_file, before_dir / f"slide_{idx}.png")
                    shutil.copy2(png_file, before_dir / f"{idx}.png")
                    shutil.copy2(png_file, after_dir / target_name)
                    shutil.copy2(png_file, after_dir / f"slide_{idx}.png")
                    shutil.copy2(png_file, after_dir / f"{idx}.png")

                    if prefix:
                        prefixed_path = previews_dir / f"slide_{idx:03d}_{prefix}.png"
                        shutil.copy2(png_file, prefixed_path)

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
                try:
                    import fitz  # type: ignore

                    doc = fitz.open(str(pdf_file))
                    for idx, page in enumerate(doc, start=1):
                        pix = page.get_pixmap(dpi=150)
                        target_name = f"slide_{idx:03d}.png"
                        target_path = previews_dir / target_name
                        pix.save(str(target_path))

                        pix.save(str(before_dir / target_name))
                        pix.save(str(before_dir / f"slide_{idx}.png"))
                        pix.save(str(before_dir / f"{idx}.png"))
                        pix.save(str(after_dir / target_name))
                        pix.save(str(after_dir / f"slide_{idx}.png"))
                        pix.save(str(after_dir / f"{idx}.png"))

                        if prefix:
                            prefixed_path = previews_dir / f"slide_{idx:03d}_{prefix}.png"
                            pix.save(str(prefixed_path))

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
                    for i in range(1, slide_count + 1):
                        img_filename = f"slide_{i:03d}.png"
                        img_path = previews_dir / img_filename
                        img_path.write_bytes(MINIMAL_PNG_BYTES)
                        (before_dir / img_filename).write_bytes(MINIMAL_PNG_BYTES)
                        (before_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
                        (before_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)
                        (after_dir / img_filename).write_bytes(MINIMAL_PNG_BYTES)
                        (after_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
                        (after_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)

                        if prefix:
                            prefixed_path = previews_dir / f"slide_{i:03d}_{prefix}.png"
                            prefixed_path.write_bytes(MINIMAL_PNG_BYTES)
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

    def _render_libreoffice_delta(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        modified_indices: list[int],
        slide_count: int = 1,
    ) -> PreviewManifest:
        previews_dir = workspace.root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        after_dir = workspace.after_previews_dir

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
                        f"LibreOffice delta conversion failed with code {result.returncode}: {result.stderr.decode('utf-8', errors='replace')}"
                    )
            except (subprocess.TimeoutExpired, TimeoutError) as exc:
                raise RenderError(f"LibreOffice delta rendering timed out after {self.timeout_seconds}s") from exc
            except Exception as exc:
                if isinstance(exc, RenderError):
                    raise
                raise RenderError(f"Subprocess error during LibreOffice delta rendering: {exc}") from exc

            pdf_file = temp_dir / f"{pptx_path.stem}.pdf"
            if not pdf_file.exists():
                generated_pdfs = list(temp_dir.glob("*.pdf"))
                if not generated_pdfs:
                    raise RenderError("LibreOffice did not produce expected PDF output")
                pdf_file = generated_pdfs[0]

            preview_items: list[SlidePreview] = []
            pdftoppm_bin = shutil.which("pdftoppm")
            mod_set = set(modified_indices) if modified_indices else set(range(1, slide_count + 1))

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
                    if idx in mod_set:
                        target_path = previews_dir / target_name
                        shutil.copy2(png_file, target_path)
                        shutil.copy2(png_file, after_dir / target_name)
                        shutil.copy2(png_file, after_dir / f"slide_{idx}.png")
                        shutil.copy2(png_file, after_dir / f"{idx}.png")

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
                try:
                    import fitz  # type: ignore

                    doc = fitz.open(str(pdf_file))
                    for idx, page in enumerate(doc, start=1):
                        target_name = f"slide_{idx:03d}.png"
                        if idx in mod_set:
                            pix = page.get_pixmap(dpi=150)
                            target_path = previews_dir / target_name
                            pix.save(str(target_path))
                            pix.save(str(after_dir / target_name))
                            pix.save(str(after_dir / f"slide_{idx}.png"))
                            pix.save(str(after_dir / f"{idx}.png"))

                        preview_items.append(
                            SlidePreview(
                                slide_index=idx,
                                image_path=f"previews/{target_name}",
                                width=1920,
                                height=1080,
                                format="png",
                            )
                        )
                    doc.close()
                except ImportError:
                    for i in range(1, slide_count + 1):
                        img_filename = f"slide_{i:03d}.png"
                        if i in mod_set:
                            img_path = previews_dir / img_filename
                            img_path.write_bytes(MINIMAL_PNG_BYTES)
                            (after_dir / img_filename).write_bytes(MINIMAL_PNG_BYTES)
                            (after_dir / f"slide_{i}.png").write_bytes(MINIMAL_PNG_BYTES)
                            (after_dir / f"{i}.png").write_bytes(MINIMAL_PNG_BYTES)
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


def build_deck_state_response(
    workspace: JobWorkspace,
    session_id: str,
    job_id: str | None = None,
    slide_count: int | None = None,
    modified_slide_indices: list[int] | None = None,
    titles: dict[int, str] | None = None,
) -> DeckStateResponse:
    """Build structured DeckStateResponse from workspace preview files and metadata."""
    if slide_count is None:
        # Check manifest or count preview files
        manifest_path = workspace.previews_dir / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                slide_count = int(data.get("slide_count", 0))
            except Exception:
                slide_count = 0

        if not slide_count:
            # Count before previews
            before_files = list(workspace.before_previews_dir.glob("slide_*.png"))
            slide_count = len(before_files) or 1

    mod_set = set(modified_slide_indices or [])
    titles_map = titles or {}

    slides: list[DeckSlideState] = []
    for idx in range(1, slide_count + 1):
        before_url = f"/api/v1/sessions/{session_id}/preview/before/{idx}.png"
        after_url = f"/api/v1/sessions/{session_id}/preview/after/{idx}.png"
        slides.append(
            DeckSlideState(
                index=idx,
                before_url=before_url,
                after_url=after_url,
                modified=(idx in mod_set),
                title=titles_map.get(idx),
            )
        )

    return DeckStateResponse(
        session_id=session_id,
        job_id=job_id,
        slide_count=slide_count,
        slides=slides,
        modified_slide_indices=sorted(list(mod_set)),
        last_modified_at=datetime.now(timezone.utc).isoformat(),
    )


def select_preview_renderer(
    prefer_real: bool = True,
    soffice_bin: str = "soffice",
    timeout_seconds: float = 30.0,
    fallback_to_mock: bool = True,
) -> BasePreviewRenderer:
    """Select appropriate preview renderer based on host capabilities and caller preferences.

    If prefer_real is True and LibreOffice plus a PDF rasterizer (pdftoppm or PyMuPDF/fitz)
    are available on the host, returns LibreOfficePreviewRenderer (with fallback_to_mock).
    Otherwise, returns MockPreviewRenderer.
    """
    if prefer_real and shutil.which(soffice_bin):
        has_pdftoppm = bool(shutil.which("pdftoppm"))
        has_fitz = False
        try:
            import fitz  # type: ignore # noqa: F401

            has_fitz = True
        except ImportError:
            pass

        if has_pdftoppm or has_fitz:
            return LibreOfficePreviewRenderer(
                soffice_bin=soffice_bin,
                timeout_seconds=timeout_seconds,
                fallback_to_mock=fallback_to_mock,
            )

    return MockPreviewRenderer()
