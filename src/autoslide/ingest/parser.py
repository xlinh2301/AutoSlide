"""OOXML PPTX shape tree and text inventory parser."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from autoslide.ingest.fingerprint import compute_shape_fingerprint
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
    TextRunInfo,
)
from autoslide.ingest.renderer import BasePreviewRenderer, MockPreviewRenderer
from autoslide.ingest.validator import validate_pptx_package
from autoslide.jobs.workspace import JobWorkspace

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _strip_ns(tag: str) -> str:
    """Return local XML tag without namespace."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


class PPTXIngestor:
    """Parses OOXML PPTX presentations into structured inventory and generates preview manifest."""

    def __init__(self, default_renderer: BasePreviewRenderer | None = None):
        self.default_renderer = default_renderer or MockPreviewRenderer()

    def parse_deck(self, pptx_path: Path) -> DeckInventory:
        """Parse deck inventory directly from PPTX path without full workspace ingestion."""
        if not pptx_path.exists():
            raise FileNotFoundError(f"PPTX file not found at {pptx_path}")
        initial_bytes = pptx_path.read_bytes()
        initial_sha256 = hashlib.sha256(initial_bytes).hexdigest()
        zf = validate_pptx_package(initial_bytes)
        try:
            return self._parse_deck(zf, initial_sha256)
        finally:
            zf.close()

    def parse(self, pptx_path: Path) -> DeckInventory:
        """Alias for parse_deck."""
        return self.parse_deck(pptx_path)

    def ingest(
        self,
        pptx_path: Path,
        workspace: JobWorkspace,
        renderer: BasePreviewRenderer | None = None,
    ) -> tuple[DeckInventory, Any]:
        """Validate, parse inventory, generate preview manifest, and store in workspace."""
        if not pptx_path.exists():
            raise FileNotFoundError(f"PPTX file not found at {pptx_path}")

        # Compute initial hash for immutability check
        initial_bytes = pptx_path.read_bytes()
        initial_sha256 = hashlib.sha256(initial_bytes).hexdigest()

        # Validate OPC package
        zf = validate_pptx_package(initial_bytes)

        try:
            inventory = self._parse_deck(zf, initial_sha256)
        finally:
            zf.close()

        # Assert immutability
        post_bytes = pptx_path.read_bytes()
        post_sha256 = hashlib.sha256(post_bytes).hexdigest()
        if post_sha256 != initial_sha256:
            raise RuntimeError(f"Input file immutability violation: {pptx_path} was modified during ingest")

        # Save inventory.json to workspace artifacts
        artifacts_dir = workspace.root / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = artifacts_dir / "inventory.json"
        inventory_path.write_text(inventory.model_dump_json(indent=2), encoding="utf-8")

        # Render preview thumbnails
        active_renderer = renderer or self.default_renderer
        preview_manifest = active_renderer.render_previews(
            pptx_path=pptx_path,
            workspace=workspace,
            slide_count=inventory.slide_count,
        )

        return inventory, preview_manifest

    def _parse_deck(self, zf: zipfile.ZipFile, source_sha256: str) -> DeckInventory:
        pres_xml_path = "ppt/presentation.xml"
        pres_tree = ET.fromstring(zf.read(pres_xml_path))

        # Dimensions
        sld_sz = pres_tree.find("p:sldSz", NS)
        if sld_sz is not None:
            cx = int(sld_sz.attrib.get("cx", 12192000))
            cy = int(sld_sz.attrib.get("cy", 6858000))
        else:
            cx = 12192000
            cy = 6858000
        dimensions = SlideDimensions(cx=cx, cy=cy)

        # Slide relationship map
        rels_map: dict[str, str] = {}
        pres_rels_path = "ppt/_rels/presentation.xml.rels"
        if pres_rels_path in zf.namelist():
            rels_tree = ET.fromstring(zf.read(pres_rels_path))
            for rel in rels_tree:
                r_id = rel.attrib.get("Id", "")
                target = rel.attrib.get("Target", "")
                if not target.startswith("ppt/"):
                    if target.startswith("/"):
                        target = target.lstrip("/")
                    else:
                        target = f"ppt/{target}"
                rels_map[r_id] = target

        # Slide ordering
        slide_items: list[SlideInventoryItem] = []
        sld_id_lst = pres_tree.find("p:sldIdLst", NS)
        if sld_id_lst is not None:
            for idx, sld_id in enumerate(sld_id_lst.findall("p:sldId", NS), start=1):
                s_id = sld_id.attrib.get("id", str(idx))
                r_id = sld_id.attrib.get(f"{{{NS['r']}}}id") or sld_id.attrib.get("r:id", "")
                slide_path = rels_map.get(r_id, f"ppt/slides/slide{idx}.xml")

                if slide_path in zf.namelist():
                    slide_tree = ET.fromstring(zf.read(slide_path))
                    shapes = self._parse_slide_shapes(slide_tree, slide_index=idx)
                    slide_items.append(
                        SlideInventoryItem(
                            slide_index=idx,
                            slide_id=s_id,
                            r_id=r_id,
                            slide_path=slide_path,
                            shapes=shapes,
                        )
                    )

        return DeckInventory(
            slide_count=len(slide_items),
            dimensions=dimensions,
            slides=slide_items,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_sha256=source_sha256,
        )

    def _parse_slide_shapes(
        self,
        slide_tree: ET.Element,
        slide_index: int,
    ) -> list[ShapeInventoryItem]:
        sp_tree = slide_tree.find(".//p:spTree", NS)
        if sp_tree is None:
            return []

        shapes: list[ShapeInventoryItem] = []
        z_counter = 0

        for child in sp_tree:
            tag = _strip_ns(child.tag)
            if tag in ("nvGrpSpPr", "grpSpPr"):
                continue

            shape_item = self._parse_single_shape(child, slide_index, z_counter, depth=0)
            if shape_item is not None:
                shapes.append(shape_item)
                z_counter += 1

        return shapes

    def _parse_single_shape(
        self,
        elem: ET.Element,
        slide_index: int,
        z_order: int,
        depth: int = 0,
    ) -> ShapeInventoryItem | None:
        if depth > 10:
            return None

        tag = _strip_ns(elem.tag)

        # 1. Non-visual properties
        nv_pr = None
        for child in elem:
            c_tag = _strip_ns(child.tag)
            if c_tag.startswith("nv") and c_tag.endswith("Pr"):
                nv_pr = child
                break

        shape_id = "0"
        shape_name = ""
        placeholder_type = None

        if nv_pr is not None:
            c_nv_pr = nv_pr.find("p:cNvPr", NS)
            if c_nv_pr is not None:
                shape_id = c_nv_pr.attrib.get("id", "0")
                shape_name = c_nv_pr.attrib.get("name", "")

            ph_elem = nv_pr.find(".//p:ph", NS)
            if ph_elem is not None:
                placeholder_type = ph_elem.attrib.get("type", "body")

        # 2. Geometry BoundingBox
        xfrm = elem.find(".//a:xfrm", NS)
        if xfrm is None:
            xfrm = elem.find("p:xfrm", NS)

        bounds = BoundingBox()
        if xfrm is not None:
            off = xfrm.find("a:off", NS)
            ext = xfrm.find("a:ext", NS)
            if off is not None:
                bounds.x = int(off.attrib.get("x", 0))
                bounds.y = int(off.attrib.get("y", 0))
            if ext is not None:
                bounds.cx = int(ext.attrib.get("cx", 0))
                bounds.cy = int(ext.attrib.get("cy", 0))

        # 3. Shape Type classification
        shape_type = tag
        table_data: list[list[str]] | None = None
        children: list[ShapeInventoryItem] | None = None

        tbl_elem = elem.find(".//a:tbl", NS)
        if tbl_elem is not None:
            shape_type = "tbl"
            table_data = []
            table_row_heights: list[int] = []
            for tr in tbl_elem.findall("a:tr", NS):
                if "h" in tr.attrib:
                    try:
                        table_row_heights.append(int(tr.attrib["h"]))
                    except ValueError:
                        pass
                row_texts: list[str] = []
                for tc in tr.findall("a:tc", NS):
                    cell_text_runs: list[str] = []
                    for t in tc.findall(".//a:t", NS):
                        if t.text:
                            cell_text_runs.append(t.text)
                    row_texts.append("".join(cell_text_runs))
                table_data.append(row_texts)
            if table_row_heights:
                bounds.cy = sum(table_row_heights)

        # 4. Text Runs & Raw Text
        text_runs: list[TextRunInfo] = []
        raw_text_parts: list[str] = []

        tx_body = elem.find("p:txBody", NS)
        if tx_body is not None:
            for p in tx_body.findall("a:p", NS):
                for r in p.findall("a:r", NS):
                    t_elem = r.find("a:t", NS)
                    text = t_elem.text if (t_elem is not None and t_elem.text) else ""
                    if not text:
                        continue

                    raw_text_parts.append(text)

                    font_name = None
                    font_size = None
                    bold = False
                    italic = False
                    color = None

                    r_pr = r.find("a:rPr", NS)
                    if r_pr is not None:
                        if "sz" in r_pr.attrib:
                            font_size = float(r_pr.attrib["sz"]) / 100.0
                        if r_pr.attrib.get("b") in ("1", "true"):
                            bold = True
                        if r_pr.attrib.get("i") in ("1", "true"):
                            italic = True

                        latin = r_pr.find("a:latin", NS)
                        if latin is not None:
                            font_name = latin.attrib.get("typeface")

                        srgb = r_pr.find(".//a:srgbClr", NS)
                        if srgb is not None:
                            color = srgb.attrib.get("val")

                    text_runs.append(
                        TextRunInfo(
                            text=text,
                            font_name=font_name,
                            font_size=font_size,
                            bold=bold,
                            italic=italic,
                            color=color,
                        )
                    )

        raw_text = "".join(raw_text_parts)
        if not raw_text and table_data:
            raw_text = " ".join(" ".join(row) for row in table_data if row).strip()

        # 5. Recursive Group Shape handling
        if tag == "grpSp":
            shape_type = "grpSp"
            children = []
            grp_z = 0
            for grp_child in elem:
                c_tag = _strip_ns(grp_child.tag)
                if c_tag in ("nvGrpSpPr", "grpSpPr"):
                    continue
                parsed_child = self._parse_single_shape(grp_child, slide_index, grp_z, depth + 1)
                if parsed_child is not None:
                    children.append(parsed_child)
                    grp_z += 1

        # 6. Composite Fingerprint
        fingerprint = compute_shape_fingerprint(
            slide_index=slide_index,
            shape_type=shape_type,
            shape_name=shape_name,
            normalized_text=raw_text,
            bounds=bounds,
            placeholder_type=placeholder_type,
        )

        return ShapeInventoryItem(
            shape_id=shape_id,
            shape_name=shape_name,
            shape_type=shape_type,
            placeholder_type=placeholder_type,
            bounds=bounds,
            z_order=z_order,
            text_runs=text_runs,
            raw_text=raw_text,
            fingerprint=fingerprint,
            table_data=table_data,
            children=children,
        )
