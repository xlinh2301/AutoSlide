"""Low-level OOXML PresentationML mutators for slide text, formatting, geometry, and structure."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from autoslide.content.models import ContentBlock
from autoslide.executor.errors import TargetNotFoundError
from autoslide.ingest.models import BoundingBox, ShapeInventoryItem
from autoslide.planner.models import (
    AddContentOp,
    AddSlideOp,
    FormatTextOp,
    MoveResizeShapeOp,
    ReorderSlideOp,
    ReplaceTextOp,
)

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Register namespaces so serialization preserves standard prefixes without ns0/ns1
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def _get_slide_path(pkg_files: dict[str, bytes], slide_index: int) -> str:
    """Locate the OOXML zip path for a 1-indexed slide."""
    pres_tree = ET.fromstring(pkg_files["ppt/presentation.xml"])
    sld_id_lst = pres_tree.find("p:sldIdLst", NS)
    if sld_id_lst is None:
        raise TargetNotFoundError("p:sldIdLst not found in presentation.xml")

    slides = sld_id_lst.findall("p:sldId", NS)
    if slide_index < 1 or slide_index > len(slides):
        raise TargetNotFoundError(f"Slide index {slide_index} out of bounds (1..{len(slides)})")

    sld_id_elem = slides[slide_index - 1]
    r_id = sld_id_elem.attrib.get(f"{{{NS['r']}}}id") or sld_id_elem.attrib.get("r:id")

    rels_tree = ET.fromstring(pkg_files["ppt/_rels/presentation.xml.rels"])
    for rel in rels_tree:
        if rel.attrib.get("Id") == r_id:
            target = rel.attrib.get("Target", "")
            if not target.startswith("ppt/"):
                if target.startswith("/"):
                    target = target.lstrip("/")
                else:
                    target = f"ppt/{target}"
            return target

    return f"ppt/slides/slide{slide_index}.xml"


def _find_shape_elem(slide_tree: ET.Element, shape_info: ShapeInventoryItem) -> ET.Element:
    """Find the specific shape XML element matching shape_id or shape_name."""
    for elem in slide_tree.findall(".//p:sp", NS) + slide_tree.findall(".//p:graphicFrame", NS) + slide_tree.findall(".//p:pic", NS):
        c_nv_pr = elem.find(".//p:cNvPr", NS)
        if c_nv_pr is not None:
            elem_id = c_nv_pr.attrib.get("id", "")
            elem_name = c_nv_pr.attrib.get("name", "")
            if (shape_info.shape_id and elem_id == shape_info.shape_id) or (shape_info.shape_name and elem_name == shape_info.shape_name):
                return elem

    # Fallback to finding by name in all children
    for elem in slide_tree.iter():
        c_nv_pr = elem.find(".//p:cNvPr", NS)
        if c_nv_pr is not None and c_nv_pr.attrib.get("name") == shape_info.shape_name:
            return elem

    raise TargetNotFoundError(f"Shape '{shape_info.shape_name}' (id: {shape_info.shape_id}) not found in slide XML")


def apply_replace_text(
    pkg_files: dict[str, bytes],
    op: ReplaceTextOp,
    shape_info: ShapeInventoryItem,
) -> dict[str, bytes]:
    """Replace text in the targeted shape while preserving existing run formatting."""
    files = dict(pkg_files)
    slide_path = _get_slide_path(files, op.target.slide_index)
    slide_tree = ET.fromstring(files[slide_path])
    shape_elem = _find_shape_elem(slide_tree, shape_info)

    tx_body = shape_elem.find("p:txBody", NS)
    if tx_body is None:
        # Support table graphicFrame elements
        tx_body = shape_elem.find(".//a:tc/a:txBody", NS)
    if tx_body is None:
        tx_body = ET.SubElement(shape_elem, f"{{{NS['p']}}}txBody")
        ET.SubElement(tx_body, f"{{{NS['a']}}}bodyPr")

    paragraphs = tx_body.findall("a:p", NS)
    if not paragraphs:
        p = ET.SubElement(tx_body, f"{{{NS['a']}}}p")
        paragraphs = [p]

    first_p = paragraphs[0]
    runs = first_p.findall("a:r", NS)

    if runs:
        # Update first run's text
        first_r = runs[0]
        t_elem = first_r.find("a:t", NS)
        if t_elem is None:
            t_elem = ET.SubElement(first_r, f"{{{NS['a']}}}t")
        t_elem.text = op.value

        # Clear remaining runs in the first paragraph to prevent duplicate trailing text
        for r in runs[1:]:
            first_p.remove(r)
    else:
        # Create a new run
        r = ET.SubElement(first_p, f"{{{NS['a']}}}r")
        r_pr = ET.SubElement(r, f"{{{NS['a']}}}rPr")
        t_elem = ET.SubElement(r, f"{{{NS['a']}}}t")
        t_elem.text = op.value

    # Remove extra trailing paragraphs if replacing full shape text
    for extra_p in paragraphs[1:]:
        tx_body.remove(extra_p)

    files[slide_path] = ET.tostring(slide_tree, encoding="utf-8", xml_declaration=True)
    return files


def apply_format_text(
    pkg_files: dict[str, bytes],
    op: FormatTextOp,
    shape_info: ShapeInventoryItem,
) -> dict[str, bytes]:
    """Update text formatting attributes (font size, bold, italic, color, font name)."""
    files = dict(pkg_files)
    slide_path = _get_slide_path(files, op.target.slide_index)
    slide_tree = ET.fromstring(files[slide_path])
    shape_elem = _find_shape_elem(slide_tree, shape_info)

    tx_body = shape_elem.find("p:txBody", NS)
    if tx_body is None:
        raise TargetNotFoundError(f"txBody not found in shape '{shape_info.shape_name}'")

    for p in tx_body.findall("a:p", NS):
        for r in p.findall("a:r", NS):
            r_pr = r.find("a:rPr", NS)
            if r_pr is None:
                r_pr = ET.Element(f"{{{NS['a']}}}rPr")
                r.insert(0, r_pr)

            if op.font_size is not None:
                r_pr.set("sz", str(int(op.font_size * 100)))

            if op.bold is not None:
                r_pr.set("b", "1" if op.bold else "0")

            if op.italic is not None:
                r_pr.set("i", "1" if op.italic else "0")

            if op.color is not None:
                clean_color = op.color.lstrip("#")
                solid_fill = r_pr.find("a:solidFill", NS)
                if solid_fill is None:
                    solid_fill = ET.SubElement(r_pr, f"{{{NS['a']}}}solidFill")
                srgb = solid_fill.find("a:srgbClr", NS)
                if srgb is None:
                    srgb = ET.SubElement(solid_fill, f"{{{NS['a']}}}srgbClr")
                srgb.set("val", clean_color)

            if op.font_name is not None:
                latin = r_pr.find("a:latin", NS)
                if latin is None:
                    latin = ET.SubElement(r_pr, f"{{{NS['a']}}}latin")
                latin.set("typeface", op.font_name)

    files[slide_path] = ET.tostring(slide_tree, encoding="utf-8", xml_declaration=True)
    return files


def apply_move_resize(
    pkg_files: dict[str, bytes],
    op: MoveResizeShapeOp,
    shape_info: ShapeInventoryItem,
) -> dict[str, bytes]:
    """Update bounding box coordinates and extents in a:xfrm."""
    files = dict(pkg_files)
    slide_path = _get_slide_path(files, op.target.slide_index)
    slide_tree = ET.fromstring(files[slide_path])
    shape_elem = _find_shape_elem(slide_tree, shape_info)

    xfrm = shape_elem.find(".//a:xfrm", NS)
    if xfrm is None:
        sp_pr = shape_elem.find("p:spPr", NS)
        if sp_pr is None:
            sp_pr = ET.SubElement(shape_elem, f"{{{NS['p']}}}spPr")
        xfrm = ET.SubElement(sp_pr, f"{{{NS['a']}}}xfrm")

    off = xfrm.find("a:off", NS)
    if off is None:
        off = ET.SubElement(xfrm, f"{{{NS['a']}}}off")

    ext = xfrm.find("a:ext", NS)
    if ext is None:
        ext = ET.SubElement(xfrm, f"{{{NS['a']}}}ext")

    if op.bounds.x is not None:
        off.set("x", str(op.bounds.x))
    if op.bounds.y is not None:
        off.set("y", str(op.bounds.y))
    if op.bounds.cx is not None:
        ext.set("cx", str(op.bounds.cx))
    if op.bounds.cy is not None:
        ext.set("cy", str(op.bounds.cy))

    files[slide_path] = ET.tostring(slide_tree, encoding="utf-8", xml_declaration=True)
    return files


def apply_duplicate_slide(
    pkg_files: dict[str, bytes],
    source_slide_index: int,
    insert_at_index: int | None = None,
) -> dict[str, bytes]:
    """Clone an existing slide XML, allocate unique relationships, and update presentation indices."""
    files = dict(pkg_files)
    src_slide_path = _get_slide_path(files, source_slide_index)

    # 1. Determine new slide filename
    existing_slide_nums = [
        int(m.group(1))
        for k in files.keys()
        if (m := re.search(r"ppt/slides/slide(\d+)\.xml$", k))
    ]
    new_num = (max(existing_slide_nums) if existing_slide_nums else 0) + 1
    new_slide_path = f"ppt/slides/slide{new_num}.xml"

    # Copy slide content
    files[new_slide_path] = files[src_slide_path]

    # Copy slide rels if present
    src_rels = src_slide_path.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    if src_rels in files:
        new_rels = f"ppt/slides/_rels/slide{new_num}.xml.rels"
        files[new_rels] = files[src_rels]

    # 2. Update presentation.xml
    pres_tree = ET.fromstring(files["ppt/presentation.xml"])
    sld_id_lst = pres_tree.find("p:sldIdLst", NS)
    if sld_id_lst is None:
        sld_id_lst = ET.SubElement(pres_tree, f"{{{NS['p']}}}sldIdLst")

    existing_ids = [int(s.attrib.get("id", 255)) for s in sld_id_lst.findall("p:sldId", NS)]
    new_id = (max(existing_ids) if existing_ids else 255) + 1

    # 3. Update presentation.xml.rels
    rels_tree = ET.fromstring(files["ppt/_rels/presentation.xml.rels"])
    existing_r_nums = [
        int(m.group(1))
        for r in rels_tree
        if (m := re.search(r"rId(\d+)$", r.attrib.get("Id", "")))
    ]
    new_r_num = (max(existing_r_nums) if existing_r_nums else 0) + 1
    new_r_id = f"rId{new_r_num}"

    # Add relationship
    new_rel = ET.SubElement(
        rels_tree,
        f"{{{NS['pr']}}}Relationship",
        {
            "Id": new_r_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            "Target": f"slides/slide{new_num}.xml",
        },
    )
    files["ppt/_rels/presentation.xml.rels"] = ET.tostring(rels_tree, encoding="utf-8", xml_declaration=True)

    # Insert into sldIdLst
    new_sld_id = ET.Element(
        f"{{{NS['p']}}}sldId",
        {
            "id": str(new_id),
            f"{{{NS['r']}}}id": new_r_id,
        },
    )

    all_slds = sld_id_lst.findall("p:sldId", NS)
    if insert_at_index is not None and 1 <= insert_at_index <= len(all_slds) + 1:
        sld_id_lst.insert(insert_at_index - 1, new_sld_id)
    else:
        sld_id_lst.append(new_sld_id)

    files["ppt/presentation.xml"] = ET.tostring(pres_tree, encoding="utf-8", xml_declaration=True)

    # 4. Update [Content_Types].xml
    ct_tree = ET.fromstring(files["[Content_Types].xml"])
    ET.SubElement(
        ct_tree,
        f"{{{NS['ct']}}}Override",
        {
            "PartName": f"/{new_slide_path}",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        },
    )
    files["[Content_Types].xml"] = ET.tostring(ct_tree, encoding="utf-8", xml_declaration=True)

    return files


def apply_delete_slide(
    pkg_files: dict[str, bytes],
    slide_index: int,
) -> dict[str, bytes]:
    """Remove a slide from presentation.xml, relations, and content types."""
    files = dict(pkg_files)
    slide_path = _get_slide_path(files, slide_index)

    # 1. Remove from presentation.xml
    pres_tree = ET.fromstring(files["ppt/presentation.xml"])
    sld_id_lst = pres_tree.find("p:sldIdLst", NS)
    if sld_id_lst is not None:
        slides = sld_id_lst.findall("p:sldId", NS)
        if 1 <= slide_index <= len(slides):
            target_elem = slides[slide_index - 1]
            r_id = target_elem.attrib.get(f"{{{NS['r']}}}id") or target_elem.attrib.get("r:id")
            sld_id_lst.remove(target_elem)
            files["ppt/presentation.xml"] = ET.tostring(pres_tree, encoding="utf-8", xml_declaration=True)

            # 2. Remove relationship
            if "ppt/_rels/presentation.xml.rels" in files:
                rels_tree = ET.fromstring(files["ppt/_rels/presentation.xml.rels"])
                for rel in list(rels_tree):
                    if rel.attrib.get("Id") == r_id:
                        rels_tree.remove(rel)
                files["ppt/_rels/presentation.xml.rels"] = ET.tostring(rels_tree, encoding="utf-8", xml_declaration=True)

    # 3. Remove file and its rels
    files.pop(slide_path, None)
    slide_rels = slide_path.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    files.pop(slide_rels, None)

    # 4. Remove from [Content_Types].xml
    if "[Content_Types].xml" in files:
        ct_tree = ET.fromstring(files["[Content_Types].xml"])
        for override in list(ct_tree):
            if override.attrib.get("PartName") == f"/{slide_path}":
                ct_tree.remove(override)
        files["[Content_Types].xml"] = ET.tostring(ct_tree, encoding="utf-8", xml_declaration=True)

    return files


def apply_reorder_slide(
    pkg_files: dict[str, bytes],
    slide_index: int,
    new_index: int,
) -> dict[str, bytes]:
    """Reorder slide position in presentation.xml p:sldIdLst."""
    files = dict(pkg_files)
    pres_tree = ET.fromstring(files["ppt/presentation.xml"])
    sld_id_lst = pres_tree.find("p:sldIdLst", NS)
    if sld_id_lst is None:
        raise TargetNotFoundError("p:sldIdLst not found in presentation.xml")

    slides = sld_id_lst.findall("p:sldId", NS)
    slide_count = len(slides)
    if slide_index < 1 or slide_index > slide_count:
        raise TargetNotFoundError(f"Slide index {slide_index} out of bounds (1..{slide_count})")

    target_elem = slides[slide_index - 1]
    sld_id_lst.remove(target_elem)

    # Normalize new_index to 1..slide_count
    if new_index < 1:
        target_pos = 0
    elif new_index > slide_count:
        target_pos = len(sld_id_lst.findall("p:sldId", NS))
    else:
        target_pos = new_index - 1

    sld_id_lst.insert(target_pos, target_elem)

    files["ppt/presentation.xml"] = ET.tostring(pres_tree, encoding="utf-8", xml_declaration=True)
    return files


def apply_add_content(
    pkg_files: dict[str, bytes],
    target_slide_index: int,
    content: ContentBlock,
    bounds: BoundingBox | None = None,
) -> dict[str, bytes]:
    """Append a new shape/text block to target slide XML."""
    supported_types = {"text", "paragraph", "title", "body", "heading", "bullet_list"}
    if content.block_type not in supported_types:
        raise ValueError(f"Unsupported content block type: '{content.block_type}'. Must be one of {sorted(supported_types)}.")

    files = dict(pkg_files)
    slide_path = _get_slide_path(files, target_slide_index)
    slide_tree = ET.fromstring(files[slide_path])

    sp_tree = slide_tree.find(".//p:spTree", NS)
    if sp_tree is None:
        raise TargetNotFoundError(f"p:spTree not found in slide {target_slide_index}")

    existing_shape_ids = []
    for elem in sp_tree.findall(".//p:cNvPr", NS):
        try:
            existing_shape_ids.append(int(elem.attrib.get("id", "0")))
        except ValueError:
            pass
    new_shape_id = (max(existing_shape_ids) if existing_shape_ids else 1) + 1
    new_shape_name = f"ContentShape {new_shape_id}"

    bx = bounds.x if bounds and bounds.x is not None else 1000000
    by = bounds.y if bounds and bounds.y is not None else 2000000
    bcx = bounds.cx if bounds and bounds.cx is not None and bounds.cx > 0 else 10000000
    bcy = bounds.cy if bounds and bounds.cy is not None and bounds.cy > 0 else 3500000

    sp = ET.SubElement(sp_tree, f"{{{NS['p']}}}sp")

    nv_sp_pr = ET.SubElement(sp, f"{{{NS['p']}}}nvSpPr")
    ET.SubElement(
        nv_sp_pr,
        f"{{{NS['p']}}}cNvPr",
        {"id": str(new_shape_id), "name": new_shape_name},
    )
    ET.SubElement(nv_sp_pr, f"{{{NS['p']}}}cNvSpPr", {"txBox": "1"})
    ET.SubElement(nv_sp_pr, f"{{{NS['p']}}}nvPr")

    sp_pr = ET.SubElement(sp, f"{{{NS['p']}}}spPr")
    xfrm = ET.SubElement(sp_pr, f"{{{NS['a']}}}xfrm")
    ET.SubElement(xfrm, f"{{{NS['a']}}}off", {"x": str(bx), "y": str(by)})
    ET.SubElement(xfrm, f"{{{NS['a']}}}ext", {"cx": str(bcx), "cy": str(bcy)})
    prst_geom = ET.SubElement(sp_pr, f"{{{NS['a']}}}prstGeom", {"prst": "rect"})
    ET.SubElement(prst_geom, f"{{{NS['a']}}}avLst")

    tx_body = ET.SubElement(sp, f"{{{NS['p']}}}txBody")
    body_pr = ET.SubElement(tx_body, f"{{{NS['a']}}}bodyPr", {"wrap": "square", "rtlCol": "0"})
    ET.SubElement(body_pr, f"{{{NS['a']}}}spAutoFit")
    ET.SubElement(tx_body, f"{{{NS['a']}}}lstStyle")

    lines = content.text.split("\n") if content.text else [""]
    for line in lines:
        p = ET.SubElement(tx_body, f"{{{NS['a']}}}p")
        if content.block_type in ("title", "heading"):
            ET.SubElement(p, f"{{{NS['a']}}}pPr", {"algn": "l"})
        r = ET.SubElement(p, f"{{{NS['a']}}}r")
        r_pr = ET.SubElement(r, f"{{{NS['a']}}}rPr")
        if content.block_type == "title":
            r_pr.set("sz", "2800")
            r_pr.set("b", "1")
        elif content.block_type == "heading":
            r_pr.set("sz", "2200")
            r_pr.set("b", "1")
        t = ET.SubElement(r, f"{{{NS['a']}}}t")
        t.text = line

    files[slide_path] = ET.tostring(slide_tree, encoding="utf-8", xml_declaration=True)
    return files


def apply_add_slide(
    pkg_files: dict[str, bytes],
    source_slide_index: int | None = None,
    insert_at_index: int = 1,
    layout_ref: str | None = None,
    content: list[ContentBlock] | None = None,
) -> dict[str, bytes]:
    """Insert a new slide with optional template/layout and initial content blocks."""
    files = dict(pkg_files)

    existing_slide_nums = [
        int(m.group(1))
        for k in files.keys()
        if (m := re.search(r"ppt/slides/slide(\d+)\.xml$", k))
    ]
    new_num = (max(existing_slide_nums) if existing_slide_nums else 0) + 1
    new_slide_path = f"ppt/slides/slide{new_num}.xml"
    new_rels_path = f"ppt/slides/_rels/slide{new_num}.xml.rels"

    if source_slide_index is not None:
        src_slide_path = _get_slide_path(files, source_slide_index)
        files[new_slide_path] = files[src_slide_path]
        src_rels = src_slide_path.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
        if src_rels in files:
            files[new_rels_path] = files[src_rels]
    else:
        found_rels = None
        for k in files.keys():
            if re.match(r"^ppt/slides/_rels/slide\d+\.xml\.rels$", k):
                found_rels = files[k]
                break

        if found_rels is not None:
            files[new_rels_path] = found_rels
        else:
            rels_root = ET.Element(f"{{{NS['pr']}}}Relationships")
            ET.SubElement(
                rels_root,
                f"{{{NS['pr']}}}Relationship",
                {
                    "Id": "rId1",
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
                    "Target": "../slideLayouts/slideLayout1.xml",
                },
            )
            files[new_rels_path] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

        minimal_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:cSld>\n'
            '    <p:spTree>\n'
            '      <p:nvGrpSpPr>\n'
            '        <p:cNvPr id="1" name=""/>\n'
            '        <p:cNvGrpSpPr/>\n'
            '        <p:nvPr/>\n'
            '      </p:nvGrpSpPr>\n'
            '      <p:grpSpPr>\n'
            '        <a:xfrm>\n'
            '          <a:off x="0" y="0"/>\n'
            '          <a:ext cx="0" cy="0"/>\n'
            '          <a:chOff x="0" y="0"/>\n'
            '          <a:chExt cx="0" cy="0"/>\n'
            '        </a:xfrm>\n'
            '      </p:grpSpPr>\n'
            '    </p:spTree>\n'
            '  </p:cSld>\n'
            '  <p:clrMapOvr>\n'
            '    <a:masterClrMapping/>\n'
            '  </p:clrMapOvr>\n'
            '</p:sld>'
        )
        files[new_slide_path] = minimal_xml.encode("utf-8")

    pres_tree = ET.fromstring(files["ppt/presentation.xml"])
    sld_id_lst = pres_tree.find("p:sldIdLst", NS)
    if sld_id_lst is None:
        sld_id_lst = ET.SubElement(pres_tree, f"{{{NS['p']}}}sldIdLst")

    existing_ids = [int(s.attrib.get("id", 255)) for s in sld_id_lst.findall("p:sldId", NS)]
    new_id = (max(existing_ids) if existing_ids else 255) + 1

    rels_tree = ET.fromstring(files["ppt/_rels/presentation.xml.rels"])
    existing_r_nums = [
        int(m.group(1))
        for r in rels_tree
        if (m := re.search(r"rId(\d+)$", r.attrib.get("Id", "")))
    ]
    new_r_num = (max(existing_r_nums) if existing_r_nums else 0) + 1
    new_r_id = f"rId{new_r_num}"

    ET.SubElement(
        rels_tree,
        f"{{{NS['pr']}}}Relationship",
        {
            "Id": new_r_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            "Target": f"slides/slide{new_num}.xml",
        },
    )
    files["ppt/_rels/presentation.xml.rels"] = ET.tostring(rels_tree, encoding="utf-8", xml_declaration=True)

    new_sld_id = ET.Element(
        f"{{{NS['p']}}}sldId",
        {
            "id": str(new_id),
            f"{{{NS['r']}}}id": new_r_id,
        },
    )

    all_slds = sld_id_lst.findall("p:sldId", NS)
    if insert_at_index is not None and 1 <= insert_at_index <= len(all_slds) + 1:
        sld_id_lst.insert(insert_at_index - 1, new_sld_id)
        effective_slide_index = insert_at_index
    elif insert_at_index is not None and insert_at_index < 1:
        sld_id_lst.insert(0, new_sld_id)
        effective_slide_index = 1
    else:
        sld_id_lst.append(new_sld_id)
        effective_slide_index = len(all_slds) + 1

    files["ppt/presentation.xml"] = ET.tostring(pres_tree, encoding="utf-8", xml_declaration=True)

    ct_tree = ET.fromstring(files["[Content_Types].xml"])
    ET.SubElement(
        ct_tree,
        f"{{{NS['ct']}}}Override",
        {
            "PartName": f"/{new_slide_path}",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        },
    )
    files["[Content_Types].xml"] = ET.tostring(ct_tree, encoding="utf-8", xml_declaration=True)

    if content:
        y_offset = 1200000
        for block in content:
            block_bounds = BoundingBox(
                x=1000000,
                y=y_offset,
                cx=10000000,
                cy=1800000 if block.block_type in ("title", "heading") else 2500000,
            )
            files = apply_add_content(
                files,
                target_slide_index=effective_slide_index,
                content=block,
                bounds=block_bounds,
            )
            y_offset += 2600000

    return files
