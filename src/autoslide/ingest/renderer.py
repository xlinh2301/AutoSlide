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


def _extract_slide_titles_and_shapes(
    pptx_path: Path,
) -> tuple[dict[int, str], dict[int, int], dict[int, list[str]]]:
    """Safely extract slide titles, shape counts, and content body items from PPTX if available."""
    titles: dict[int, str] = {}
    shape_counts: dict[int, int] = {}
    slide_texts: dict[int, list[str]] = {}
    if not pptx_path.exists() or not zipfile.is_zipfile(pptx_path):
        return titles, shape_counts, slide_texts
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

                    # Extract all non-empty paragraphs
                    all_paragraphs: list[str] = []
                    for p in root.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}p"):
                        t_nodes = p.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                        p_txt = "".join(t.text for t in t_nodes if t.text).strip()
                        if p_txt:
                            all_paragraphs.append(p_txt)

                    # Filter out pure page numbers (e.g. '01', '02', '1')
                    meaningful = [t for t in all_paragraphs if not (t.isdigit() and len(t) <= 3)]

                    title_text = ""
                    for sp in shapes:
                        ph = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}ph")
                        if ph is not None and ph.get("type") in ("title", "ctrTitle"):
                            texts = [
                                t.text
                                for t in sp.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                                if t.text
                            ]
                            cand = " ".join(texts).strip()
                            if cand and not (cand.isdigit() and len(cand) <= 3):
                                title_text = cand
                                break

                    if not title_text and meaningful:
                        title_text = meaningful[0][:65]

                    if not title_text:
                        title_text = f"Slide {idx}"

                    titles[idx] = title_text

                    # Body items are all remaining paragraphs after title
                    body: list[str] = []
                    for t in meaningful:
                        if t != title_text and t not in body:
                            body.append(t)
                    slide_texts[idx] = body
                except Exception:
                    continue
    except Exception:
        pass
    return titles, shape_counts, slide_texts


def generate_mock_slide_card(
    slide_index: int,
    title: str | None = None,
    subtitle: str | None = None,
    shape_count: int | None = None,
    is_modified: bool = False,
    body_items: list[str] | None = None,
    theme: str = "light",
    width: int = 1280,
    height: int = 720,
) -> bytes:
    """Generate a rich 16:9 slide card preview image with real content in Canva Presentation style."""
    is_dark = (theme == "dark")
    bg_color = "#18181b" if is_dark else "#ffffff"
    border_outline = "#f59e0b" if is_modified else ("#27272a" if is_dark else "#e2e8f0")
    border_width = 3 if is_modified else 2

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    font_badge = _get_font(14, bold=True)
    font_title = _get_font(30, bold=True)
    font_sub = _get_font(16, bold=False)
    font_card_head = _get_font(18, bold=True)
    font_body = _get_font(16, bold=False)
    font_footer = _get_font(13, bold=False)

    # 1. Slide canvas border
    card_margin = 24
    draw.rounded_rectangle(
        [(card_margin, card_margin), (width - card_margin, height - card_margin)],
        radius=14,
        outline=border_outline,
        width=border_width,
    )

    # Top neon-amber accent indicator bar if modified
    if is_modified:
        draw.rounded_rectangle(
            [
                (card_margin + 6, card_margin + 4),
                (width - card_margin - 6, card_margin + 12),
            ],
            radius=4,
            fill="#f59e0b",
        )

    # 2. Slide badge pill: 'SLIDE X'
    badge_x = card_margin + 32
    badge_y = card_margin + 24
    badge_w = 100
    badge_h = 30
    badge_bg = "#27272a" if is_dark else "#f1f5f9"
    badge_fg = "#ffffff" if is_dark else "#475569"
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=12,
        fill=badge_bg,
        outline="#3f3f46" if is_dark else "#cbd5e1",
        width=1,
    )
    draw.text(
        (badge_x + 16, badge_y + 6),
        f"SLIDE {slide_index}",
        fill=badge_fg,
        font=font_badge,
    )

    # Modified pill if modified
    if is_modified:
        amber_x = badge_x + badge_w + 12
        amber_w = 110
        draw.rounded_rectangle(
            [(amber_x, badge_y), (amber_x + amber_w, badge_y + badge_h)],
            radius=12,
            fill="#f59e0b",
        )
        draw.text(
            (amber_x + 16, badge_y + 6),
            "MODIFIED",
            fill="#18181b",
            font=font_badge,
        )

    # 3. Slide Title
    slide_title = (title or f"Slide {slide_index} Overview").strip()
    if len(slide_title) > 65:
        slide_title = slide_title[:62] + "..."
    title_y = badge_y + badge_h + 16
    title_color = "#f4f4f5" if is_dark else "#0f172a"
    draw.text(
        (badge_x, title_y),
        slide_title,
        fill=title_color,
        font=font_title,
    )

    # 4. Subtitle / Metadata
    sub_y = title_y + 40
    if subtitle:
        sub_text = subtitle
    elif shape_count is not None and shape_count > 0:
        sub_text = f"{shape_count} shape{'s' if shape_count != 1 else ''} • 16:9 Canva Presentation"
    else:
        sub_text = f"16:9 Canva Presentation • Slide {slide_index}"
    sub_color = "#a1a1aa" if is_dark else "#64748b"
    draw.text(
        (badge_x, sub_y),
        sub_text,
        fill=sub_color,
        font=font_sub,
    )

    # 5. Divider
    div_y = sub_y + 30
    draw.line(
        [(badge_x, div_y), (width - card_margin - 32, div_y)],
        fill="#27272a" if is_dark else "#e2e8f0",
        width=1,
    )

    # 6. Body Content Cards (Canva Presentation Layout)
    content_top = div_y + 18
    content_bottom = height - card_margin - 36
    content_w = (width - card_margin - 32) - badge_x

    items = [it.strip() for it in (body_items or []) if it.strip()]

    card_bg = "#1f1f23" if is_dark else "#f8fafc"
    card_border = "#2e2e33" if is_dark else "#e2e8f0"
    card_head_color = "#f4f4f5" if is_dark else "#0f172a"
    text_color = "#d4d4d8" if is_dark else "#334155"

    def _render_text_block(x: int, y: int, max_w: int, text_lines: list[str], accent_color: str):
        # Draw top accent bar on card
        draw.rounded_rectangle([(x + 20, y), (x + 80, y + 4)], radius=2, fill=accent_color)
        cur_y = y + 22
        for line in text_lines:
            if cur_y > content_bottom - 35:
                break
            is_header = len(line) < 30 and not line.endswith((".", ",", ";")) and not line.startswith("•")
            if is_header:
                cur_y += 4
                draw.text((x + 20, cur_y), line.upper(), fill=card_head_color, font=font_card_head)
                cur_y += 30
            else:
                clean_line = line.lstrip("•-* ").strip()
                words = clean_line.split()
                wrapped = []
                cur_line: list[str] = []
                for w in words:
                    cur_line.append(w)
                    if len(" ".join(cur_line)) > 42:
                        wrapped.append(" ".join(cur_line[:-1]))
                        cur_line = [w]
                if cur_line:
                    wrapped.append(" ".join(cur_line))

                for l_idx, wl in enumerate(wrapped[:5]):
                    prefix = "•  " if l_idx == 0 else "   "
                    draw.text((x + 24, cur_y), f"{prefix}{wl}", fill=text_color, font=font_body)
                    cur_y += 24
                cur_y += 8

    if not items:
        # Default structured cards when slide has no body text
        col_gap = 20
        col_w = (content_w - col_gap) // 2
        col1_left = badge_x
        col2_left = badge_x + col_w + col_gap
        draw.rounded_rectangle(
            [(col1_left, content_top), (col1_left + col_w, content_bottom)],
            radius=12,
            fill=card_bg,
            outline=card_border,
            width=1,
        )
        _render_text_block(col1_left, content_top, col_w, [
            "Overview & Key Points",
            "Extracted presentation content and structured visual hierarchy.",
            "Professional Canva presentation design with optimized contrast.",
        ], "#3b82f6")
        draw.rounded_rectangle(
            [(col2_left, content_top), (col2_left + col_w, content_bottom)],
            radius=12,
            fill=card_bg,
            outline=card_border,
            width=1,
        )
        _render_text_block(col2_left, content_top, col_w, [
            "Presentation Notes",
            "16:9 widescreen layout with high-definition typography.",
            "AI transformation ready for targeted slide edits and polishing.",
        ], "#10b981")
    elif len(items) <= 2:
        # Single wide card
        draw.rounded_rectangle(
            [(badge_x, content_top), (badge_x + content_w, content_bottom)],
            radius=12,
            fill=card_bg,
            outline=card_border,
            width=1,
        )
        _render_text_block(badge_x, content_top, content_w, items, "#3b82f6")
    else:
        # Two balanced columns
        col_gap = 20
        col_w = (content_w - col_gap) // 2
        col1_left = badge_x
        col2_left = badge_x + col_w + col_gap
        mid = (len(items) + 1) // 2
        items_c1 = items[:mid]
        items_c2 = items[mid:]

        draw.rounded_rectangle(
            [(col1_left, content_top), (col1_left + col_w, content_bottom)],
            radius=12,
            fill=card_bg,
            outline=card_border,
            width=1,
        )
        _render_text_block(col1_left, content_top, col_w, items_c1, "#3b82f6")

        draw.rounded_rectangle(
            [(col2_left, content_top), (col2_left + col_w, content_bottom)],
            radius=12,
            fill=card_bg,
            outline=card_border,
            width=1,
        )
        _render_text_block(col2_left, content_top, col_w, items_c2, "#10b981")

    # 7. Footer
    footer_y = height - card_margin - 20
    draw.text((badge_x, footer_y), "AutoSlide Studio • Canva Edition", fill="#94a3b8", font=font_footer)
    draw.text((width - card_margin - 120, footer_y), f"Slide {slide_index}", fill="#94a3b8", font=font_footer)

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

        titles, shape_counts, slide_texts = _extract_slide_titles_and_shapes(pptx_path)

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            png_bytes = generate_mock_slide_card(
                slide_index=i,
                title=titles.get(i),
                shape_count=shape_counts.get(i),
                is_modified=False,
                body_items=slide_texts.get(i, []),
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

        titles, shape_counts, slide_texts = _extract_slide_titles_and_shapes(pptx_path)

        preview_items: list[SlidePreview] = []
        for i in range(1, slide_count + 1):
            base_filename = f"slide_{i:03d}.png"
            if not modified_indices or i in modified_indices:
                png_bytes = generate_mock_slide_card(
                    slide_index=i,
                    title=titles.get(i),
                    shape_count=shape_counts.get(i),
                    is_modified=True,
                    body_items=slide_texts.get(i, []),
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
