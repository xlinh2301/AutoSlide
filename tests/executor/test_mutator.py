"""Tests for low-level OOXML mutators."""

from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import pytest

from autoslide.executor.mutator import (
    apply_delete_slide,
    apply_duplicate_slide,
    apply_format_text,
    apply_move_resize,
    apply_replace_text,
)
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.validator import validate_pptx_package
from autoslide.jobs.workspace import JobWorkspace
from autoslide.planner.models import (
    BoundingBoxUpdate,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceTextOp,
    TargetReference,
)
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def test_apply_replace_text_preserves_formatting(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_mut_001")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)

    title_shape = inventory.slides[0].shapes[0]
    fp = title_shape.fingerprint

    op = ReplaceTextOp(
        target=TargetReference(slide_index=1, object_ref=fp),
        value="New Updated Deck Title",
    )

    zf = zipfile.ZipFile(pptx_file, "r")
    pkg_files = {name: zf.read(name) for name in zf.namelist()}
    zf.close()

    updated_files = apply_replace_text(pkg_files, op, title_shape)
    
    # Repackage and inspect with PPTXIngestor
    out_file = tmp_path / "mutated.pptx"
    with zipfile.ZipFile(out_file, "w") as out_zf:
        for name, content in updated_files.items():
            out_zf.writestr(name, content)

    mut_inv, _ = ingestor.ingest(out_file, workspace)
    mut_shape = mut_inv.slides[0].shapes[0]

    assert mut_shape.raw_text == "New Updated Deck Title"
    assert len(mut_shape.text_runs) >= 1
    # Formatting preserved
    assert mut_shape.text_runs[0].bold is True
    assert mut_shape.text_runs[0].font_size == 44.0
    assert mut_shape.text_runs[0].font_name == "Arial"
    assert mut_shape.text_runs[0].color == "112233"


def test_apply_format_text(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_mut_002")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)

    title_shape = inventory.slides[0].shapes[0]
    op = FormatTextOp(
        target=TargetReference(slide_index=1, object_ref=title_shape.fingerprint),
        font_size=28.0,
        italic=True,
        color="FF5500",
    )

    zf = zipfile.ZipFile(pptx_file, "r")
    pkg_files = {name: zf.read(name) for name in zf.namelist()}
    zf.close()

    updated_files = apply_format_text(pkg_files, op, title_shape)
    out_file = tmp_path / "mutated_fmt.pptx"
    with zipfile.ZipFile(out_file, "w") as out_zf:
        for name, content in updated_files.items():
            out_zf.writestr(name, content)

    mut_inv, _ = ingestor.ingest(out_file, workspace)
    mut_shape = mut_inv.slides[0].shapes[0]
    assert mut_shape.text_runs[0].font_size == 28.0
    assert mut_shape.text_runs[0].italic is True
    assert mut_shape.text_runs[0].color == "FF5500"


def test_apply_move_resize(tmp_path: Path):
    pptx_bytes = create_minimal_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_mut_003")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)

    title_shape = inventory.slides[0].shapes[0]
    op = MoveResizeShapeOp(
        target=TargetReference(slide_index=1, object_ref=title_shape.fingerprint),
        bounds=BoundingBoxUpdate(x=1500000, y=800000, cx=9000000, cy=1800000),
    )

    zf = zipfile.ZipFile(pptx_file, "r")
    pkg_files = {name: zf.read(name) for name in zf.namelist()}
    zf.close()

    updated_files = apply_move_resize(pkg_files, op, title_shape)
    out_file = tmp_path / "mutated_geom.pptx"
    with zipfile.ZipFile(out_file, "w") as out_zf:
        for name, content in updated_files.items():
            out_zf.writestr(name, content)

    mut_inv, _ = ingestor.ingest(out_file, workspace)
    mut_shape = mut_inv.slides[0].shapes[0]
    assert mut_shape.bounds.x == 1500000
    assert mut_shape.bounds.y == 800000
    assert mut_shape.bounds.cx == 9000000
    assert mut_shape.bounds.cy == 1800000


def test_apply_duplicate_slide(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "deck3.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_mut_004")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)
    assert inventory.slide_count == 3

    zf = zipfile.ZipFile(pptx_file, "r")
    pkg_files = {name: zf.read(name) for name in zf.namelist()}
    zf.close()

    updated_files = apply_duplicate_slide(pkg_files, source_slide_index=1, insert_at_index=2)
    out_file = tmp_path / "duplicated.pptx"
    with zipfile.ZipFile(out_file, "w") as out_zf:
        for name, content in updated_files.items():
            out_zf.writestr(name, content)

    validate_pptx_package(out_file)
    mut_inv, _ = ingestor.ingest(out_file, workspace)
    assert mut_inv.slide_count == 4


def test_apply_delete_slide(tmp_path: Path):
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "deck3.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_mut_005")
    ingestor = PPTXIngestor()
    inventory, _ = ingestor.ingest(pptx_file, workspace)
    assert inventory.slide_count == 3

    zf = zipfile.ZipFile(pptx_file, "r")
    pkg_files = {name: zf.read(name) for name in zf.namelist()}
    zf.close()

    updated_files = apply_delete_slide(pkg_files, slide_index=2)
    out_file = tmp_path / "deleted.pptx"
    with zipfile.ZipFile(out_file, "w") as out_zf:
        for name, content in updated_files.items():
            out_zf.writestr(name, content)

    validate_pptx_package(out_file)
    mut_inv, _ = ingestor.ingest(out_file, workspace)
    assert mut_inv.slide_count == 2
