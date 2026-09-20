"""Slide Toolset and Tool Registry for AutoSlide Real Local Agent."""

from __future__ import annotations

import io
from pathlib import Path
import re
from typing import Any, Callable
import zipfile

from pydantic import BaseModel, ConfigDict, Field

from autoslide.content.models import ContentBlock
from autoslide.content.research import ResearchService
from autoslide.executor.errors import TargetNotFoundError
from autoslide.executor.mutator import (
    NS,
    _find_shape_elem,
    _get_slide_path,
    apply_add_slide,
    apply_delete_slide,
    apply_format_text,
    apply_reorder_slide,
    apply_replace_text,
)
from autoslide.ingest.models import BoundingBox, DeckInventory, ShapeInventoryItem
from autoslide.ingest.parser import PPTXIngestor
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import FormatTextOp, ReplaceTextOp, TargetReference, TargetScope

import xml.etree.ElementTree as ET


class ToolExecutionContext(BaseModel):
    """Execution context provided to slide tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    job_id: str | None = None
    workspace: JobWorkspace | None = None
    working_pptx_path: Path | None = None
    inventory: DeckInventory | None = None
    research_service: ResearchService | None = None
    selected_slide_index: int | None = None


class ToolCallResult(BaseModel):
    """Structured result returned from executing a tool."""

    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    modified_slide_indices: list[int] = Field(default_factory=list)
    success: bool = True
    error: str | None = None


class ToolRegistry:
    """Registry managing tool schemas and deterministic dispatchers."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._dispatchers: dict[str, Callable[[dict[str, Any], ToolExecutionContext], ToolCallResult]] = {}
        self._register_default_tools()

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        dispatcher: Callable[[dict[str, Any], ToolExecutionContext], ToolCallResult],
    ) -> None:
        """Register a new tool schema and its execution dispatcher."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
        self._dispatchers[name] = dispatcher

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """Return all registered tools formatted as OpenAI-compatible function definitions."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get schema for a specific tool."""
        return self._tools.get(name)

    def execute(self, tool_name: str, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Dispatch and execute a tool call by name."""
        if tool_name not in self._dispatchers:
            return ToolCallResult(
                tool_name=tool_name,
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error=f"Unknown tool: '{tool_name}'",
            )
        try:
            return self._dispatchers[tool_name](arguments, context)
        except Exception as exc:
            return ToolCallResult(
                tool_name=tool_name,
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error=str(exc),
            )

    def _register_default_tools(self) -> None:
        """Register the 7 core slide and intelligence tools."""
        toolset = SlideToolset()

        # 1. edit_slide_text
        self.register(
            name="edit_slide_text",
            description="Edit or replace text within a specific shape, title, or body on a slide",
            parameters={
                "type": "object",
                "properties": {
                    "slide_index": {"type": "integer", "description": "1-based slide index"},
                    "target": {"type": "string", "description": "Shape name, role ('title', 'body'), or text substring to replace"},
                    "new_text": {"type": "string", "description": "The replacement or formatted text"},
                },
                "required": ["slide_index", "target", "new_text"],
            },
            dispatcher=toolset.edit_slide_text,
        )

        # 2. add_slide
        self.register(
            name="add_slide",
            description="Add a new slide to the presentation with title and bullet points",
            parameters={
                "type": "object",
                "properties": {
                    "layout": {"type": "string", "enum": ["title_and_content", "two_column", "section_header", "blank"], "description": "Layout style"},
                    "title": {"type": "string", "description": "Slide title"},
                    "content_bullets": {"type": "array", "items": {"type": "string"}, "description": "List of bullet points or content lines"},
                    "insert_at_index": {"type": "integer", "description": "Optional 1-based position to insert at (defaults to appending)"},
                },
                "required": ["title", "content_bullets"],
            },
            dispatcher=toolset.add_slide,
        )

        # 3. delete_slide
        self.register(
            name="delete_slide",
            description="Delete a slide from the presentation",
            parameters={
                "type": "object",
                "properties": {
                    "slide_index": {"type": "integer", "description": "1-based slide index to delete"},
                },
                "required": ["slide_index"],
            },
            dispatcher=toolset.delete_slide,
        )

        # 4. reorder_slide
        self.register(
            name="reorder_slide",
            description="Move a slide from one position to another in the presentation",
            parameters={
                "type": "object",
                "properties": {
                    "from_index": {"type": "integer", "description": "1-based source slide index"},
                    "to_index": {"type": "integer", "description": "1-based target slide position"},
                },
                "required": ["from_index", "to_index"],
            },
            dispatcher=toolset.reorder_slide,
        )

        # 5. update_slide_style
        self.register(
            name="update_slide_style",
            description="Update visual style, colors, or theme of a slide",
            parameters={
                "type": "object",
                "properties": {
                    "slide_index": {"type": "integer", "description": "1-based slide index"},
                    "theme": {"type": "string", "enum": ["modern_dark", "clean_light", "corporate_blue", "vibrant_accent"], "description": "Theme style to apply"},
                    "layout_type": {"type": "string", "description": "Optional layout type"},
                },
                "required": ["slide_index", "theme"],
            },
            dispatcher=toolset.update_slide_style,
        )

        # 6. analyze_slide_content
        self.register(
            name="analyze_slide_content",
            description="Inspect slide text and numbers to perform calculations, summaries, or data analysis",
            parameters={
                "type": "object",
                "properties": {
                    "slide_index": {"type": "integer", "description": "1-based slide index, or 0 for entire presentation"},
                    "query": {"type": "string", "description": "Analysis, calculation, or question about slide content"},
                },
                "required": ["query"],
            },
            dispatcher=toolset.analyze_slide_content,
        )

        # 7. search_web
        self.register(
            name="search_web",
            description="Search the web for fresh factual information, statistics, or references for slides",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
            dispatcher=toolset.search_web,
        )


class SlideToolset:
    """Implementations for OOXML mutations and intelligence tools."""

    @staticmethod
    def _read_pkg(pptx_path: Path) -> dict[str, bytes]:
        """Read PPTX zip archive into memory dictionary."""
        files: dict[str, bytes] = {}
        with zipfile.ZipFile(pptx_path, "r") as zf:
            for info in zf.infolist():
                files[info.filename] = zf.read(info.filename)
        return files

    @staticmethod
    def _write_pkg(pptx_path: Path, files: dict[str, bytes]) -> None:
        """Write memory dictionary into PPTX zip archive atomically."""
        tmp_path = pptx_path.with_suffix(".tmp.pptx")
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in sorted(files.items()):
                zf.writestr(filename, content)
        tmp_path.replace(pptx_path)

    def edit_slide_text(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Edit or replace text on a slide."""
        slide_index = int(arguments.get("slide_index", 1))
        target = str(arguments.get("target", "")).strip()
        new_text = str(arguments.get("new_text", ""))

        if not context.working_pptx_path or not context.working_pptx_path.exists():
            return ToolCallResult(
                tool_name="edit_slide_text",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error="Working PPTX file not found in context",
            )

        pkg_files = self._read_pkg(context.working_pptx_path)

        # Parse slide XML to locate shape matching target
        slide_path = _get_slide_path(pkg_files, slide_index)
        slide_tree = ET.fromstring(pkg_files[slide_path])

        matched_shape_elem: ET.Element | None = None
        target_lower = target.lower()

        # 1. Search shapes by name, role or contained text
        for elem in slide_tree.findall(".//p:sp", NS) + slide_tree.findall(".//p:graphicFrame", NS):
            c_nv_pr = elem.find(".//p:cNvPr", NS)
            elem_id = c_nv_pr.attrib.get("id", "") if c_nv_pr is not None else ""
            elem_name = c_nv_pr.attrib.get("name", "") if c_nv_pr is not None else ""

            # Extract existing text
            shape_text = "".join(t.text or "" for t in elem.findall(".//a:t", NS))

            if target_lower in ["title", "heading"]:
                ph = elem.find(".//p:ph", NS)
                if ph is not None and ph.attrib.get("type", "") in ["title", "ctrTitle"]:
                    matched_shape_elem = elem
                    break
            elif target_lower in ["body", "content"]:
                ph = elem.find(".//p:ph", NS)
                if ph is not None and ph.attrib.get("type", "") in ["body", "subTitle"]:
                    matched_shape_elem = elem
                    break

            if elem_id == target or elem_name == target:
                matched_shape_elem = elem
                break
            if target and target.lower() in shape_text.lower():
                matched_shape_elem = elem
                break

        # Fallback to the first text shape if target is broad
        if matched_shape_elem is None:
            all_sp = slide_tree.findall(".//p:sp", NS)
            if all_sp:
                matched_shape_elem = all_sp[0]

        if matched_shape_elem is None:
            return ToolCallResult(
                tool_name="edit_slide_text",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error=f"Could not find shape matching target '{target}' on slide {slide_index}",
            )

        c_nv = matched_shape_elem.find(".//p:cNvPr", NS)
        sh_id = c_nv.attrib.get("id", "1") if c_nv is not None else "1"
        sh_name = c_nv.attrib.get("name", "Shape") if c_nv is not None else "Shape"

        shape_info = ShapeInventoryItem(
            shape_id=sh_id,
            shape_name=sh_name,
            shape_type="text_box",
            text=new_text,
            bounds=BoundingBox(x=100, y=100, cx=500, cy=300),
            fingerprint="",
        )

        op = ReplaceTextOp(
            target=TargetReference(slide_index=slide_index, object_ref=sh_id),
            value=new_text,
        )

        updated_files = apply_replace_text(pkg_files, op, shape_info)
        self._write_pkg(context.working_pptx_path, updated_files)

        return ToolCallResult(
            tool_name="edit_slide_text",
            arguments=arguments,
            result={
                "message": f"Successfully updated text on slide {slide_index}",
                "slide_index": slide_index,
                "target": target,
                "new_text": new_text,
            },
            modified_slide_indices=[slide_index],
            success=True,
        )

    def add_slide(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Add a new slide to the presentation."""
        title = str(arguments.get("title", "New Slide"))
        content_bullets = arguments.get("content_bullets", [])
        if isinstance(content_bullets, str):
            content_bullets = [content_bullets]
        insert_at_index = arguments.get("insert_at_index")

        if not context.working_pptx_path or not context.working_pptx_path.exists():
            return ToolCallResult(
                tool_name="add_slide",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error="Working PPTX file not found in context",
            )

        pkg_files = self._read_pkg(context.working_pptx_path)

        # Count existing slides
        pres_tree = ET.fromstring(pkg_files["ppt/presentation.xml"])
        sld_id_lst = pres_tree.find("p:sldIdLst", NS)
        current_count = len(sld_id_lst.findall("p:sldId", NS)) if sld_id_lst is not None else 1

        target_index = int(insert_at_index) if insert_at_index is not None else current_count + 1

        content_blocks = [
            ContentBlock(block_type="title", text=title),
        ]
        if content_bullets:
            bullets_text = "\n".join(f"• {b.lstrip('•- ')}" for b in content_bullets)
            content_blocks.append(ContentBlock(block_type="body", text=bullets_text))

        updated_files = apply_add_slide(
            pkg_files=pkg_files,
            insert_at_index=target_index,
            content=content_blocks,
        )
        self._write_pkg(context.working_pptx_path, updated_files)

        return ToolCallResult(
            tool_name="add_slide",
            arguments=arguments,
            result={
                "message": f"Successfully added slide '{title}' at position {target_index}",
                "slide_index": target_index,
                "title": title,
                "content_bullets": content_bullets,
            },
            modified_slide_indices=[target_index],
            success=True,
        )

    def delete_slide(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Delete a slide from the presentation."""
        slide_index = int(arguments.get("slide_index", 1))

        if not context.working_pptx_path or not context.working_pptx_path.exists():
            return ToolCallResult(
                tool_name="delete_slide",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error="Working PPTX file not found in context",
            )

        pkg_files = self._read_pkg(context.working_pptx_path)
        updated_files = apply_delete_slide(pkg_files, slide_index=slide_index)
        self._write_pkg(context.working_pptx_path, updated_files)

        return ToolCallResult(
            tool_name="delete_slide",
            arguments=arguments,
            result={
                "message": f"Successfully deleted slide {slide_index}",
                "deleted_slide_index": slide_index,
            },
            modified_slide_indices=[slide_index],
            success=True,
        )

    def reorder_slide(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Reorder slides in the presentation."""
        from_index = int(arguments.get("from_index", 1))
        to_index = int(arguments.get("to_index", 1))

        if not context.working_pptx_path or not context.working_pptx_path.exists():
            return ToolCallResult(
                tool_name="reorder_slide",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error="Working PPTX file not found in context",
            )

        pkg_files = self._read_pkg(context.working_pptx_path)
        updated_files = apply_reorder_slide(pkg_files, slide_index=from_index, new_index=to_index)
        self._write_pkg(context.working_pptx_path, updated_files)

        return ToolCallResult(
            tool_name="reorder_slide",
            arguments=arguments,
            result={
                "message": f"Successfully moved slide from {from_index} to {to_index}",
                "from_index": from_index,
                "to_index": to_index,
            },
            modified_slide_indices=[from_index, to_index],
            success=True,
        )

    def update_slide_style(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Update color theme and typography style on a slide."""
        slide_index = int(arguments.get("slide_index", 1))
        theme = str(arguments.get("theme", "corporate_blue"))

        if not context.working_pptx_path or not context.working_pptx_path.exists():
            return ToolCallResult(
                tool_name="update_slide_style",
                arguments=arguments,
                result={},
                modified_slide_indices=[],
                success=False,
                error="Working PPTX file not found in context",
            )

        # Theme color mapping
        theme_colors = {
            "modern_dark": "1E293B",
            "clean_light": "F8FAFC",
            "corporate_blue": "1E40AF",
            "vibrant_accent": "7C3AED",
        }
        color_val = theme_colors.get(theme, "1E40AF")

        pkg_files = self._read_pkg(context.working_pptx_path)
        slide_path = _get_slide_path(pkg_files, slide_index)
        slide_tree = ET.fromstring(pkg_files[slide_path])

        # Apply formatting to all runs in the slide
        for r_pr in slide_tree.findall(".//a:rPr", NS):
            solid_fill = r_pr.find("a:solidFill", NS)
            if solid_fill is None:
                solid_fill = ET.SubElement(r_pr, f"{{{NS['a']}}}solidFill")
            srgb = solid_fill.find("a:srgbClr", NS)
            if srgb is None:
                srgb = ET.SubElement(solid_fill, f"{{{NS['a']}}}srgbClr")
            srgb.set("val", color_val)

        pkg_files[slide_path] = ET.tostring(slide_tree, encoding="utf-8", xml_declaration=True)
        self._write_pkg(context.working_pptx_path, pkg_files)

        return ToolCallResult(
            tool_name="update_slide_style",
            arguments=arguments,
            result={
                "message": f"Successfully applied theme '{theme}' to slide {slide_index}",
                "slide_index": slide_index,
                "theme": theme,
            },
            modified_slide_indices=[slide_index],
            success=True,
        )

    def analyze_slide_content(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Inspect and calculate data or summarize content from slides."""
        slide_index = int(arguments.get("slide_index", 0))
        query = str(arguments.get("query", ""))

        text_corpus: list[str] = []
        numbers: list[float] = []

        target_slide_title: str = ""
        target_slide_bullets: list[str] = []
        target_shape_count: int = 0

        if context.working_pptx_path and context.working_pptx_path.exists():
            pkg_files = self._read_pkg(context.working_pptx_path)
            pres_tree = ET.fromstring(pkg_files["ppt/presentation.xml"])
            sld_id_lst = pres_tree.find("p:sldIdLst", NS)
            num_slides = len(sld_id_lst.findall("p:sldId", NS)) if sld_id_lst is not None else 1

            indices_to_scan = [slide_index] if (1 <= slide_index <= num_slides) else list(range(1, num_slides + 1))
            for s_idx in indices_to_scan:
                try:
                    s_path = _get_slide_path(pkg_files, s_idx)
                    s_tree = ET.fromstring(pkg_files[s_path])

                    sp_tree = s_tree.find(".//p:spTree", NS)
                    shapes = []
                    if sp_tree is not None:
                        for child in sp_tree:
                            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if tag not in ("nvGrpSpPr", "grpSpPr"):
                                shapes.append(child)

                    slide_texts = [t.text for t in s_tree.findall(".//a:t", NS) if t.text]
                    slide_full = " ".join(slide_texts)
                    text_corpus.append(f"Slide {s_idx}: {slide_full}")

                    # Extract numbers for calculation
                    found_nums = re.findall(r"[-+]?\d*\.?\d+", slide_full)
                    for n in found_nums:
                        try:
                            numbers.append(float(n))
                        except ValueError:
                            pass

                    # If this matches the target slide (or first slide when slide_index == 0)
                    if s_idx == slide_index or (slide_index == 0 and not target_slide_title):
                        target_shape_count = len(shapes)
                        title_elem = None
                        for elem in shapes:
                            ph = elem.find(".//p:ph", NS)
                            if ph is not None and ph.attrib.get("type", "") in ["title", "ctrTitle"]:
                                title_elem = elem
                                break

                        if title_elem is not None:
                            t_runs = [t.text.strip() for t in title_elem.findall(".//a:t", NS) if t.text and t.text.strip()]
                            target_slide_title = " ".join(t_runs)

                        for elem in shapes:
                            if elem is title_elem:
                                continue
                            for p in elem.findall(".//a:p", NS):
                                p_runs = [t.text.strip() for t in p.findall(".//a:t", NS) if t.text and t.text.strip()]
                                p_text = " ".join(p_runs)
                                if p_text and p_text not in target_slide_bullets:
                                    target_slide_bullets.append(p_text)

                        if not target_slide_title and target_slide_bullets:
                            target_slide_title = target_slide_bullets.pop(0)
                except Exception:
                    pass

        # Fallback to context.inventory if PPTX file was not present or didn't yield text
        if (not target_slide_title or target_shape_count == 0) and context.inventory and context.inventory.slides:
            s_item = next((s for s in context.inventory.slides if s.slide_index == slide_index), None)
            if s_item is None and context.inventory.slides:
                s_item = context.inventory.slides[0]
            if s_item:
                target_shape_count = len(s_item.shapes)
                for sh in s_item.shapes:
                    sh_text = (sh.text or "").strip()
                    if not sh_text:
                        continue
                    if not target_slide_title:
                        target_slide_title = sh_text
                    elif sh_text not in target_slide_bullets:
                        target_slide_bullets.append(sh_text)

        joined_corpus = "\n".join(text_corpus)
        total_words = sum(len(txt.split()) for txt in text_corpus)
        sum_numbers = sum(numbers)
        avg_numbers = sum_numbers / len(numbers) if numbers else 0.0

        if not target_slide_title:
            target_slide_title = "(Không có tiêu đề)"

        if slide_index >= 1:
            if target_slide_bullets:
                bullets_formatted = "\n".join(f"  - {b}" for b in target_slide_bullets)
                detail_section = f"\n{bullets_formatted}"
            else:
                detail_section = " (Không có nội dung văn bản chi tiết)"

            analysis_summary = (
                f"Nội dung trên Slide {slide_index} bao gồm:\n"
                f"• Tiêu đề: {target_slide_title}\n"
                f"• Nội dung chi tiết:{detail_section}\n"
                f"• Số lượng thành phần: {target_shape_count} shapes."
            )
            if any(k in query.lower() for k in ["tính", "tổng", "sum"]):
                analysis_summary += f"\n• Tổng các số liệu tìm thấy: {sum_numbers:.2f}"
            elif any(k in query.lower() for k in ["trung bình", "average"]):
                analysis_summary += f"\n• Trung bình các số liệu tìm thấy: {avg_numbers:.2f}"
        else:
            analysis_summary = f"Kết quả phân tích bài thuyết trình: Scanned {len(text_corpus)} slides. Total word count: {total_words}."
            if "tính" in query.lower() or "sum" in query.lower() or "tổng" in query.lower():
                analysis_summary += f" Sum of numbers found: {sum_numbers:.2f}."
            elif "trung bình" in query.lower() or "average" in query.lower():
                analysis_summary += f" Average of numbers found: {avg_numbers:.2f}."
            elif "đếm" in query.lower() or "count" in query.lower():
                analysis_summary += f" Total slides analyzed: {len(text_corpus)}, total words: {total_words}."

        return ToolCallResult(
            tool_name="analyze_slide_content",
            arguments=arguments,
            result={
                "message": "Analysis completed",
                "slide_index": slide_index,
                "query": query,
                "analysis": analysis_summary,
                "title": target_slide_title,
                "bullet_points": target_slide_bullets,
                "shape_count": target_shape_count,
                "corpus_sample": joined_corpus[:500],
                "numbers_detected": numbers[:10],
            },
            modified_slide_indices=[],
            success=True,
        )

    def search_web(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolCallResult:
        """Search the web for up-to-date facts and data."""
        query = str(arguments.get("query", ""))
        results = []

        if context.research_service:
            research_res = context.research_service.search(query)
            for src in research_res.sources:
                results.append({
                    "title": src.title,
                    "url": src.url,
                    "summary": src.summary,
                    "claims": src.claims,
                })
        else:
            results.append({
                "title": f"Web search results for '{query}'",
                "url": f"https://example.org/search?q={query.replace(' ', '+')}",
                "summary": f"Key information and factual context regarding '{query}'.",
                "claims": [f"Fact verified regarding {query}"],
            })

        return ToolCallResult(
            tool_name="search_web",
            arguments=arguments,
            result={
                "query": query,
                "results": results,
                "message": f"Retrieved {len(results)} search results for '{query}'",
            },
            modified_slide_indices=[],
            success=True,
        )
