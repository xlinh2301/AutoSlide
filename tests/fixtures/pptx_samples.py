"""Dynamic PPTX fixture generator for testing."""

from __future__ import annotations

import io
from pathlib import Path
import zipfile


def create_minimal_pptx() -> bytes:
    """Create a minimal valid 1-slide PPTX package in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>""",
        )

        # _rels/.rels
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
        )

        # ppt/presentation.xml
        zf.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldSz cx="12192000" cy="6858000"/>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId1"/>
  </p:sldIdLst>
</p:presentation>""",
        )

        # ppt/_rels/presentation.xml.rels
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>""",
        )

        # ppt/slides/slide1.xml
        zf.writestr(
            "ppt/slides/slide1.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title 1"/>
          <p:cNvSpPr>
            <a:spLocks noGrp="1"/>
          </p:cNvSpPr>
          <p:nvPr>
            <p:ph type="ctrTitle"/>
          </p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="2000000" y="1000000"/>
            <a:ext cx="8000000" cy="1500000"/>
          </a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="en-US" sz="4400" b="1">
                <a:solidFill>
                  <a:srgbClr val="112233"/>
                </a:solidFill>
                <a:latin typeface="Arial"/>
              </a:rPr>
              <a:t>Sample Deck Title</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>""",
        )

    return buf.getvalue()


def create_complex_multi_slide_pptx() -> bytes:
    """Create a 3-slide PPTX package with shapes, tables, groups, text formatting, and images."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slides/slide3.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>""",
        )

        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
        )

        zf.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldSz cx="9144000" cy="6858000"/>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId1"/>
    <p:sldId id="257" r:id="rId2"/>
    <p:sldId id="258" r:id="rId3"/>
  </p:sldIdLst>
</p:presentation>""",
        )

        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide3.xml"/>
</Relationships>""",
        )

        # Slide 1: Title & Subtitle
        zf.writestr(
            "ppt/slides/slide1.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title 1"/>
          <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
          <p:nvPr><p:ph type="title"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="500000" y="500000"/><a:ext cx="8000000" cy="1000000"/></a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:bodyPr/>
          <a:p>
            <a:r>
              <a:rPr sz="3600" b="1"><a:latin typeface="Calibri"/></a:rPr>
              <a:t>Executive Summary</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="3" name="Subtitle 2"/>
          <p:cNvSpPr/>
          <p:nvPr><p:ph type="subTitle"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="500000" y="1600000"/><a:ext cx="8000000" cy="800000"/></a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:bodyPr/>
          <a:p>
            <a:r>
              <a:rPr sz="2000" i="1"/>
              <a:t>Q3 Strategic Performance</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>""",
        )

        # Slide 2: Table and Picture
        zf.writestr(
            "ppt/slides/slide2.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:graphicFrame>
        <p:nvGraphicFramePr>
          <p:cNvPr id="4" name="Financial Table"/>
          <p:cNvGraphicFramePr/>
          <p:nvPr/>
        </p:nvGraphicFramePr>
        <p:xfrm><a:off x="1000000" y="1000000"/><a:ext cx="6000000" cy="3000000"/></p:xfrm>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
            <a:tbl>
              <a:tblPr/>
              <a:tblGrid><a:gridCol w="3000000"/><a:gridCol w="3000000"/></a:tblGrid>
              <a:tr h="1000000">
                <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Metric</a:t></a:r></a:p></a:txBody></a:tc>
                <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Value</a:t></a:r></a:p></a:txBody></a:tc>
              </a:tr>
              <a:tr h="1000000">
                <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Revenue</a:t></a:r></a:p></a:txBody></a:tc>
                <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>$12.5M</a:t></a:r></a:p></a:txBody></a:tc>
              </a:tr>
            </a:tbl>
          </a:graphicData>
        </a:graphic>
      </p:graphicFrame>
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="5" name="Chart Icon"/>
          <p:cNvPicPr/>
          <p:nvPr/>
        </p:nvPicPr>
        <p:blipFill>
          <a:blip r:embed="rIdImg1"/>
          <a:stretch><a:fillRect/></a:stretch>
        </p:blipFill>
        <p:spPr>
          <a:xfrm><a:off x="7200000" y="1000000"/><a:ext cx="1500000" cy="1500000"/></a:xfrm>
        </p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
</p:sld>""",
        )

        # Slide 3: Nested Group Shape (grpSp)
        zf.writestr(
            "ppt/slides/slide3.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:grpSp>
        <p:nvGrpSpPr>
          <p:cNvPr id="6" name="Card Group 1"/>
          <p:cNvGrpSpPr/>
          <p:nvPr/>
        </p:nvGrpSpPr>
        <p:grpSpPr>
          <a:xfrm><a:off x="500000" y="500000"/><a:ext cx="4000000" cy="3000000"/></a:xfrm>
        </p:grpSpPr>
        <p:sp>
          <p:nvSpPr><p:cNvPr id="7" name="Card Header"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
          <p:spPr><a:xfrm><a:off x="500000" y="500000"/><a:ext cx="4000000" cy="800000"/></a:xfrm></p:spPr>
          <p:txBody><a:bodyPr/><a:p><a:r><a:t>Group Item 1</a:t></a:r></a:p></p:txBody>
        </p:sp>
        <p:sp>
          <p:nvSpPr><p:cNvPr id="8" name="Card Body"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
          <p:spPr><a:xfrm><a:off x="500000" y="1400000"/><a:ext cx="4000000" cy="2000000"/></a:xfrm></p:spPr>
          <p:txBody><a:bodyPr/><a:p><a:r><a:t>Description inside group</a:t></a:r></a:p></p:txBody>
        </p:sp>
      </p:grpSp>
    </p:spTree>
  </p:cSld>
</p:sld>""",
        )

    return buf.getvalue()


def create_corrupt_zip() -> bytes:
    """Create an invalid truncated non-zip byte sequence."""
    return b"PK\x03\x04\x14\x00\x00\x00corrupted-non-zip-payload"


def create_missing_content_types_pptx() -> bytes:
    """Create a zip package without [Content_Types].xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_rels/.rels", "<rels/>")
        zf.writestr("ppt/presentation.xml", "<presentation/>")
    return buf.getvalue()


def create_malformed_xml_pptx() -> bytes:
    """Create a PPTX package with malformed XML in presentation.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
</Types>""",
        )
        zf.writestr("ppt/presentation.xml", "<p:presentation>unclosed xml tag")
    return buf.getvalue()


def create_encrypted_package() -> bytes:
    """Create a simulated encrypted OOXML package."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("EncryptedPackage", b"\x00" * 256)
    return buf.getvalue()
