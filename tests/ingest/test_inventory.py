"""Tests for PPTX slide and object inventory extraction and fingerprint stability."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from autoslide.ingest.fingerprint import compute_shape_fingerprint
from autoslide.ingest.models import BoundingBox, DeckInventory
from autoslide.ingest.parser import PPTXIngestor
from autoslide.jobs.workspace import JobWorkspace
from tests.fixtures.pptx_samples import (
    create_complex_multi_slide_pptx,
    create_minimal_pptx,
)


def test_compute_shape_fingerprint_deterministic():
    bounds = BoundingBox(x=100, y=200, cx=300, cy=400)
    fp1 = compute_shape_fingerprint(
        slide_index=1,
        shape_type="sp",
        shape_name="Title 1",
        normalized_text="  Sample Title Text  \n",
        bounds=bounds,
        placeholder_type="title",
    )
    fp2 = compute_shape_fingerprint(
        slide_index=1,
        shape_type="sp",
        shape_name="Title 1",
        normalized_text="sample   title   text",
        bounds=bounds,
        placeholder_type="title",
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # sha256 hex length


def test_compute_shape_fingerprint_differs_on_variation():
    bounds1 = BoundingBox(x=100, y=200, cx=300, cy=400)
    bounds2 = BoundingBox(x=100, y=200, cx=300, cy=500)
    fp1 = compute_shape_fingerprint(
        slide_index=1,
        shape_type="sp",
        shape_name="Title 1",
        normalized_text="Sample Title",
        bounds=bounds1,
    )
    fp2 = compute_shape_fingerprint(
        slide_index=1,
        shape_type="sp",
        shape_name="Title 1",
        normalized_text="Sample Title",
        bounds=bounds2,
    )
    assert fp1 != fp2


def test_parse_minimal_pptx(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_test_001")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)

    assert inventory.slide_count == 1
    assert inventory.dimensions.cx == 12192000
    assert inventory.dimensions.cy == 6858000
    assert len(inventory.slides) == 1

    slide = inventory.slides[0]
    assert slide.slide_index == 1
    assert len(slide.shapes) >= 1

    title_shape = slide.shapes[0]
    assert title_shape.shape_name == "Title 1"
    assert title_shape.placeholder_type == "ctrTitle"
    assert title_shape.bounds.x == 2000000
    assert title_shape.bounds.y == 1000000
    assert title_shape.bounds.cx == 8000000
    assert title_shape.bounds.cy == 1500000
    assert "Sample Deck Title" in title_shape.raw_text
    assert len(title_shape.text_runs) >= 1
    assert title_shape.text_runs[0].bold is True
    assert title_shape.text_runs[0].font_size == 44.0
    assert title_shape.text_runs[0].font_name == "Arial"
    assert title_shape.text_runs[0].color == "112233"
    assert title_shape.fingerprint is not None


def test_parse_complex_multi_slide_pptx(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "complex.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_test_002")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)

    assert inventory.slide_count == 3
    assert len(inventory.slides) == 3

    # Slide 1 checks
    s1 = inventory.slides[0]
    assert len(s1.shapes) == 2
    assert s1.shapes[0].shape_name == "Title 1"
    assert s1.shapes[0].placeholder_type == "title"
    assert s1.shapes[0].raw_text == "Executive Summary"
    assert s1.shapes[1].shape_name == "Subtitle 2"
    assert s1.shapes[1].placeholder_type == "subTitle"
    assert s1.shapes[1].raw_text == "Q3 Strategic Performance"

    # Slide 2 checks (Table + Picture)
    s2 = inventory.slides[1]
    assert len(s2.shapes) == 2
    tbl_shape = next(s for s in s2.shapes if s.shape_type == "tbl" or s.shape_type == "graphicFrame")
    assert tbl_shape.table_data is not None
    assert tbl_shape.table_data == [["Metric", "Value"], ["Revenue", "$12.5M"]]

    pic_shape = next(s for s in s2.shapes if s.shape_type == "pic")
    assert pic_shape.shape_name == "Chart Icon"

    # Slide 3 checks (Group shape recursive parsing)
    s3 = inventory.slides[2]
    assert len(s3.shapes) >= 1
    grp_shape = s3.shapes[0]
    assert grp_shape.shape_type == "grpSp"
    assert grp_shape.children is not None
    assert len(grp_shape.children) == 2
    assert grp_shape.children[0].shape_name == "Card Header"
    assert grp_shape.children[0].raw_text == "Group Item 1"
    assert grp_shape.children[1].shape_name == "Card Body"
    assert grp_shape.children[1].raw_text == "Description inside group"


def test_inventory_fingerprint_stability_across_runs(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    file_path = tmp_path / "input.pptx"
    file_path.write_bytes(pptx_bytes)

    ws1 = JobWorkspace.create(tmp_path, "job_ws1")
    ws2 = JobWorkspace.create(tmp_path, "job_ws2")

    ingestor = PPTXIngestor()
    inv1, _ = ingestor.ingest(file_path, ws1)
    inv2, _ = ingestor.ingest(file_path, ws2)

    fps1 = [s.fingerprint for slide in inv1.slides for s in slide.shapes]
    fps2 = [s.fingerprint for slide in inv2.slides for s in slide.shapes]
    assert fps1 == fps2


def test_input_file_immutability(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = tmp_path / "unmodified.pptx"
    input_file.write_bytes(pptx_bytes)

    initial_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()
    initial_stat = input_file.stat()

    workspace = JobWorkspace.create(tmp_path, "job_immutability")
    ingestor = PPTXIngestor()
    ingestor.ingest(input_file, workspace)

    post_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()
    post_stat = input_file.stat()

    assert initial_hash == post_hash
    assert initial_stat.st_size == post_stat.st_size

    # Check that inventory.json was generated in artifacts
    inv_file = workspace.root / "artifacts" / "inventory.json"
    assert inv_file.exists()
