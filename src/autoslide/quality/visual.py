"""Visual quality gate evaluating rendered slides and layout geometry."""

from __future__ import annotations

from autoslide.ingest.models import DeckInventory, PreviewManifest
from autoslide.quality.models import (
    FindingCategory,
    FindingSeverity,
    VisualFinding,
    VisualGateResult,
)


class VisualQualityGate:
    """Evaluates rendered slides and deck inventory geometry for visual defects."""

    def __init__(self, char_width_factor: float = 0.55, line_height_factor: float = 1.2):
        self.char_width_factor = char_width_factor
        self.line_height_factor = line_height_factor

    def evaluate(
        self,
        inventory: DeckInventory,
        preview_manifest: PreviewManifest | None = None,
    ) -> VisualGateResult:
        findings: list[VisualFinding] = []
        slide_w = inventory.dimensions.cx
        slide_h = inventory.dimensions.cy

        for slide in inventory.slides:
            for shape in slide.shapes:
                # 1. Check Bounds Clipping (shape extends beyond slide canvas)
                x = shape.bounds.x
                y = shape.bounds.y
                cx = shape.bounds.cx
                cy = shape.bounds.cy

                if x + cx > slide_w or y + cy > slide_h or x < 0 or y < 0:
                    findings.append(
                        VisualFinding(
                            slide_index=slide.slide_index,
                            shape_name=shape.shape_name,
                            object_ref=shape.fingerprint,
                            category=FindingCategory.BOUNDS_CLIPPING,
                            severity=FindingSeverity.ERROR,
                            message=(
                                f"Shape '{shape.shape_name}' bounds (x={x}, y={y}, cx={cx}, cy={cy}) "
                                f"exceed slide dimensions ({slide_w}x{slide_h})."
                            ),
                            suggested_fix="Adjust shape position or reduce dimensions to fit within slide boundary.",
                        )
                    )

                # 2. Check Text Overflow (text length exceeds estimated capacity)
                raw_text = shape.raw_text.strip() if shape.raw_text else ""
                if raw_text and cx > 0 and cy > 0:
                    # Determine effective font size in EMU (1 pt = 12,700 EMU)
                    font_size_pt = 18.0
                    if shape.text_runs and shape.text_runs[0].font_size:
                        font_size_pt = float(shape.text_runs[0].font_size)

                    font_size_emu = font_size_pt * 12700.0
                    char_w_emu = font_size_emu * self.char_width_factor
                    line_h_emu = font_size_emu * self.line_height_factor

                    line_capacity = max(1, int(cy // line_h_emu))
                    chars_per_line = max(1, int(cx // char_w_emu))
                    max_capacity = chars_per_line * line_capacity

                    estimated_text_width = len(raw_text) * char_w_emu
                    available_width = cx * line_capacity

                    if estimated_text_width > available_width * 1.05:
                        overflow_pct = int(((estimated_text_width / available_width) - 1.0) * 100)
                        findings.append(
                            VisualFinding(
                                slide_index=slide.slide_index,
                                shape_name=shape.shape_name,
                                object_ref=shape.fingerprint,
                                category=FindingCategory.TEXT_OVERFLOW,
                                severity=FindingSeverity.ERROR,
                                message=(
                                    f"Text overflows bounding box by approx {overflow_pct}% "
                                    f"(chars={len(raw_text)}, capacity={max_capacity})."
                                ),
                                suggested_fix="Reduce font size by 20% or enlarge bounding box.",
                            )
                        )

        # 3. Check Render Failures (via PreviewManifest if supplied)
        if preview_manifest:
            if preview_manifest.slide_count < inventory.slide_count:
                findings.append(
                    VisualFinding(
                        slide_index=0,
                        shape_name="DeckRenderer",
                        object_ref=None,
                        category=FindingCategory.RENDER_FAILURE,
                        severity=FindingSeverity.CRITICAL,
                        message=(
                            f"Render preview incomplete: generated {preview_manifest.slide_count} "
                            f"slides out of {inventory.slide_count}."
                        ),
                        suggested_fix="Check headless LibreOffice / Poppler render environment.",
                    )
                )

        has_critical_or_error = any(
            f.severity in (FindingSeverity.CRITICAL, FindingSeverity.ERROR) for f in findings
        )
        passed = not has_critical_or_error

        return VisualGateResult(
            passed=passed,
            findings=findings,
            has_critical_or_error=has_critical_or_error,
        )
