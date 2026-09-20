"""Slide preview rendering adapters and manifest generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageDraw, ImageFont

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


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Safely obtain font with graceful fallback to default font."""
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
        if bold
        else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans.ttf",
        "Arial.ttf",
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _extract_slide_titles_and_shapes(pptx_path: Path) -> tuple[dict[int, str], dict[int, int]]:
    """Safely extract slide titles and shape counts from PPTX if available."""
    titles: dict[int, str] = {}
    shape_counts: dict[int, int] = {}
    if not pptx_path.exists() or not zipfile.is_zipfile(pptx_path):
        return titles, shape_counts
    try:
        with zipfile.ZipFile(pptx_path) as zf:
            slide_entries = [
                n
                for n in zf.namelist()
                if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            ]
            for name in slide_entries:
                try:
                    num_str = "".join(filter(str.isdigit, Path(name).stem))
                    idx = int(num_str) if num_str else len(titles) + 1
                    xml_content = zf.read(name)
                    root = ET.fromstring(xml_content)
                    shapes = root.findall(".//{http://schemas.openxmlformats.org/presentationml/2006/main}sp")
                    shape_counts[idx] = len(shapes)
                    title_text = ""
                    for sp in shapes:
                        ph = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}ph")
                        if ph is not None and ph.get("type") in ("title", "ctrTitle"):
                            texts = [
                                t.text
                                for t in sp.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                                if t.text
                            ]
                            if texts:
                                title_text = " ".join(texts).strip()
                                break
                    if not title_text:
                        first_texts = [
                            t.text
                            for t in root.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                            if t.text
                        ]
                        if first_texts:
                            candidate = " ".join(first_texts[:3]).strip()
                            if candidate:
                                title_text = candidate[:40]
                    if title_text:
                        titles[idx] = title_text
                except Exception:
                    continue
    except Exception:
        pass
    return titles, shape_counts


def generate_mock_slide_card(
    slide_index: int,
    title: str | None = None,
    subtitle: str | None = None,
    shape_count: int | None = None,
    is_modified: bool = False,
    width: int = 1280,
    height: int = 720,
) -> bytes:
    """Generate a rich 16:9 slide card preview image using PIL.Image and PIL.ImageDraw."""
    # 1. 1280x720 RGB image with dark background (#18181b)
    img = Image.new("RGB", (width, height), color="#18181b")
    draw = ImageDraw.Draw(img)

    font_badge = _get_font(15, bold=True)
    font_title = _get_font(34, bold=True)
    font_sub = _get_font(18, bold=False)

    # 2. Subtle rounded rectangle border (#27272a)
    card_margin = 28
    border_outline = "#f59e0b" if is_modified else "#27272a"
    border_width = 3 if is_modified else 2
    draw.rounded_rectangle(
        [(card_margin, card_margin), (width - card_margin, height - card_margin)],
        radius=16,
        outline=border_outline,
        width=border_width,
    )

    # Top neon-amber accent indicator bar if modified
    if is_modified:
        draw.rounded_rectangle(
            [
                (card_margin + 4, card_margin + 4),
                (width - card_margin - 4, card_margin + 12),
            ],
            radius=4,
            fill="#f59e0b",
        )

    # 3. Slide badge pill: 'SLIDE X' (#3f3f46 background, #ffffff text)
    badge_x = card_margin + 36
    badge_y = card_margin + 36
    badge_w = 110
    badge_h = 32
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=14,
        fill="#3f3f46",
    )
    draw.text(
        (badge_x + 18, badge_y + 7),
        f"SLIDE {slide_index}",
        fill="#ffffff",
        font=font_badge,
    )

    # Neon-amber indicator pill if modified
    if is_modified:
        amber_x = badge_x + badge_w + 12
        amber_w = 116
        draw.rounded_rectangle(
            [(amber_x, badge_y), (amber_x + amber_w, badge_y + badge_h)],
            radius=14,
            fill="#f59e0b",
        )
        draw.text(
            (amber_x + 16, badge_y + 7),
            "MODIFIED",
            fill="#18181b",
            font=font_badge,
        )

    # 4. Slide title if known or 'Slide X Overview' in bold clean text (#f4f4f5)
    slide_title = (title or f"Slide {slide_index} Overview").strip()
    if len(slide_title) > 60:
        slide_title = slide_title[:57] + "..."
    title_y = badge_y + badge_h + 24
    draw.text(
        (badge_x, title_y),
        slide_title,
        fill="#f4f4f5",
        font=font_title,
    )

    # 5. Brief subtitle or shape count placeholder (#a1a1aa)
    if subtitle:
        sub_text = subtitle
    elif shape_count is not None and shape_count > 0:
        sub_text = f"{shape_count} shape{'s' if shape_count != 1 else ''} • 16:9 widescreen layout"
    else:
        sub_text = f"Shape count placeholder • 16:9 widescreen slide {slide_index}"

    sub_y = title_y + 46
    draw.text(
        (badge_x, sub_y),
        sub_text,
        fill="#a1a1aa",
        font=font_sub,
    )

    # Wireframe preview shape cards
    content_top = sub_y + 44
    content_bottom = height - card_margin - 36
    content_width = width - (badge_x * 2)
    col_gap = 24
    col_w = (content_width - col_gap) // 2
    col1_left = badge_x
    col2_left = badge_x + col_w + col_gap

    # Left card
    draw.rounded_rectangle(
        [(col1_left, content_top), (col1_left + col_w, content_bottom)],
        radius=12,
        fill="#1f1f23",
        outline="#2e2e33",
        width=1,
    )
    draw.rounded_rectangle(
        [(col1_left + 24, content_top + 24), (col1_left + col_w - 24, content_top + 160)],
        radius=8,
        fill="#27272a",
        outline="#f59e0b" if is_modified else "#3f3f46",
        width=1,
    )
    draw.rounded_rectangle(
        [(col1_left + 24, content_top + 180), (col1_left + 220, content_top + 194)],
        radius=4,
        fill="#3f3f46",
    )
    draw.rounded_rectangle(
        [(col1_left + 24, content_top + 208), (col1_left + col_w - 40, content_top + 220)],
        radius=4,
        fill="#2e2e33",
    )
    draw.rounded_rectangle(
        [(col1_left + 24, content_top + 232), (col1_left + col_w - 90, content_top + 244)],
        radius=4,
        fill="#2e2e33",
    )

    # Right card
    draw.rounded_rectangle(
        [(col2_left, content_top), (col2_left + col_w, content_bottom)],
        radius=12,
        fill="#1f1f23",
        outline="#2e2e33",
        width=1,
    )
    draw.rounded_rectangle(
        [(col2_left + 24, content_top + 24), (col2_left + 160, content_top + 70)],
        radius=6,
        fill="#27272a",
    )
    draw.rounded_rectangle(
        [(col2_left + 180, content_top + 24), (col2_left + 320, content_top + 70)],
        radius=6,
        fill="#27272a",
    )
    draw.rounded_rectangle(
        [(col2_left + 24, content_top + 90), (col2_left + col_w - 24, content_bottom - 24)],
        radius=8,
        fill="#27272a",
        outline="#3f3f46",
        width=1,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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

        titles, shape_counts = _extract_slide_titles_and_shapes(pptx_path)

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            png_bytes = generate_mock_slide_card(
                slide_index=i,
                title=titles.get(i),
                shape_count=shape_counts.get(i),
                is_modified=False,
            )

            img_path = previews_dir / base_filename
            img_path.write_bytes(png_bytes)

            # Write dual Before and After previews
            (before_dir / base_filename).write_bytes(png_bytes)
            (before_dir / f"slide_{i}.png").write_bytes(png_bytes)
            (before_dir / f"{i}.png").write_bytes(png_bytes)
            (after_dir / base_filename).write_bytes(png_bytes)
            (after_dir / f"slide_{i}.png").write_bytes(png_bytes)
            (after_dir / f"{i}.png").write_bytes(png_bytes)

            if prefix:
                prefixed_filename = f"slide_{i:03d}_{prefix}.png"
                (previews_dir / prefixed_filename).write_bytes(png_bytes)

            preview_items.append(
                SlidePreview(
                    slide_index=i,
                    image_path=f"previews/{base_filename}",
                    width=1280,
                    height=720,
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

        titles, shape_counts = _extract_slide_titles_and_shapes(pptx_path)

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            if not modified_indices or i in modified_indices:
                png_bytes = generate_mock_slide_card(
                    slide_index=i,
                    title=titles.get(i),
                    shape_count=shape_counts.get(i),
                    is_modified=True,
                )
                img_path = previews_dir / base_filename
                img_path.write_bytes(png_bytes)
                (after_dir / base_filename).write_bytes(png_bytes)
                (after_dir / f"slide_{i}.png").write_bytes(png_bytes)
                (after_dir / f"{i}.png").write_bytes(png_bytes)

            preview_items.append(
                SlidePreview(
                    slide_index=i,
                    image_path=f"previews/{base_filename}",
                    width=1280,
                    height=720,
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
