"""Unit tests for Slide Toolset and Tool Registry."""

from __future__ import annotations

from pathlib import Path
import pytest
import zipfile
import xml.etree.ElementTree as ET

from autoslide.agent.tools import (
    SlideToolset,
    ToolExecutionContext,
    ToolRegistry,
)
from autoslide.executor.mutator import NS
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


@pytest.fixture
def sample_pptx_workspace(tmp_path: Path) -> tuple[Path, ToolExecutionContext]:
    """Create a temporary workspace with working PPTX file."""
    working_dir = tmp_path / "working"
    working_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = working_dir / "presentation.pptx"
    pptx_path.write_bytes(create_complex_multi_slide_pptx())

    context = ToolExecutionContext(
        session_id="test_session_123",
        job_id="test_job_123",
        working_pptx_path=pptx_path,
    )
    return pptx_path, context


def test_tool_registry_schemas():
    """Verify ToolRegistry registers all 7 slide tools with valid JSON schemas."""
    registry = ToolRegistry()
    schemas = registry.get_tools_schema()

    assert len(schemas) == 7
    tool_names = {t["name"] for t in schemas}
    assert tool_names == {
        "edit_slide_text",
        "add_slide",
        "delete_slide",
        "reorder_slide",
        "update_slide_style",
        "analyze_slide_content",
        "search_web",
    }

    for tool in schemas:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert "properties" in tool["parameters"]
        assert "required" in tool["parameters"]


def test_edit_slide_text_tool(sample_pptx_workspace):
    """Test edit_slide_text updates slide title in the OOXML package."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "edit_slide_text",
        {
            "slide_index": 1,
            "target": "title",
            "new_text": "Updated Financial Overview Q3",
        },
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == [1]
    assert result.result["new_text"] == "Updated Financial Overview Q3"

    # Verify text was written into ppt/slides/slide1.xml
    with zipfile.ZipFile(pptx_path, "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Updated Financial Overview Q3" in slide_xml


def test_add_slide_tool(sample_pptx_workspace):
    """Test add_slide appends a new slide with title and bullet points."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "add_slide",
        {
            "title": "Next Steps & Key Milestones",
            "content_bullets": ["Complete API integration", "Run browser QA tests"],
            "layout": "title_and_content",
        },
        context,
    )

    assert result.success is True
    assert len(result.modified_slide_indices) == 1
    assert result.modified_slide_indices[0] == 4  # 3 original slides + 1 appended

    with zipfile.ZipFile(pptx_path, "r") as zf:
        pres_tree = ET.fromstring(zf.read("ppt/presentation.xml"))
        sld_id_lst = pres_tree.find("p:sldIdLst", NS)
        assert len(sld_id_lst.findall("p:sldId", NS)) == 4


def test_delete_slide_tool(sample_pptx_workspace):
    """Test delete_slide removes the designated slide from presentation."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "delete_slide",
        {"slide_index": 2},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == [2]

    with zipfile.ZipFile(pptx_path, "r") as zf:
        pres_tree = ET.fromstring(zf.read("ppt/presentation.xml"))
        sld_id_lst = pres_tree.find("p:sldIdLst", NS)
        assert len(sld_id_lst.findall("p:sldId", NS)) == 2


def test_reorder_slide_tool(sample_pptx_workspace):
    """Test reorder_slide shifts slide from position 1 to 3."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "reorder_slide",
        {"from_index": 1, "to_index": 3},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == [1, 3]


def test_update_slide_style_tool(sample_pptx_workspace):
    """Test update_slide_style applies theme color palette."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "update_slide_style",
        {"slide_index": 1, "theme": "modern_dark"},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == [1]

    with zipfile.ZipFile(pptx_path, "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "1E293B" in slide_xml


def test_analyze_slide_content_tool(sample_pptx_workspace):
    """Test analyze_slide_content calculates totals and analyzes corpus."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "analyze_slide_content",
        {"slide_index": 0, "query": "Hãy tính tổng các số liệu và đếm từ"},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == []
    assert "analysis" in result.result
    assert "Scanned" in result.result["analysis"]


def test_analyze_slide_content_target_slide(sample_pptx_workspace):
    """Test analyze_slide_content extracts title, bullets, and shape count for target slide."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "analyze_slide_content",
        {"slide_index": 1, "query": "slide 1 có gì"},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == []
    assert "title" in result.result
    assert "bullet_points" in result.result
    assert "shape_count" in result.result
    assert "Nội dung trên Slide 1 bao gồm:" in result.result["analysis"]
    assert "• Tiêu đề:" in result.result["analysis"]
    assert "• Nội dung chi tiết:" in result.result["analysis"]



def test_search_web_tool(sample_pptx_workspace):
    """Test search_web returns search findings and references."""
    pptx_path, context = sample_pptx_workspace
    registry = ToolRegistry()

    result = registry.execute(
        "search_web",
        {"query": "Generative AI presentation market trends 2026"},
        context,
    )

    assert result.success is True
    assert result.modified_slide_indices == []
    assert len(result.result["results"]) > 0


def test_unknown_tool_and_missing_file():
    """Test error handling when tool is unknown or working PPTX is missing."""
    registry = ToolRegistry()
    context = ToolExecutionContext(session_id="s1", working_pptx_path=Path("/non/existent.pptx"))

    # Unknown tool
    res_unknown = registry.execute("unknown_tool", {}, context)
    assert res_unknown.success is False
    assert "Unknown tool" in res_unknown.error

    # Missing PPTX
    res_missing = registry.execute("edit_slide_text", {"slide_index": 1, "target": "t", "new_text": "n"}, context)
    assert res_missing.success is False
    assert "Working PPTX file not found" in res_missing.error
