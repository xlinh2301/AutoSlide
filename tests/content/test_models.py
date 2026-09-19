import pytest
from pydantic import ValidationError
from autoslide.planner.models import TargetReference
from autoslide.content.models import (
    ContentOrigin,
    SourceRecord,
    ResearchResult,
    GeneratedContent,
    ProvenanceRecord,
)


def test_content_origin_valid_kinds():
    origin_user = ContentOrigin(kind="USER")
    assert origin_user.kind == "USER"
    assert origin_user.source_ids == []
    assert origin_user.runtime_name is None

    origin_web = ContentOrigin(kind="WEB", source_ids=["src-1", "src-2"])
    assert origin_web.kind == "WEB"
    assert origin_web.source_ids == ["src-1", "src-2"]

    origin_ai = ContentOrigin(kind="AI_GENERATED", runtime_name="gemini")
    assert origin_ai.kind == "AI_GENERATED"
    assert origin_ai.runtime_name == "gemini"


def test_content_origin_invalid_kind():
    with pytest.raises(ValidationError):
        ContentOrigin(kind="UNKNOWN_KIND")  # type: ignore


def test_content_origin_immutable():
    origin = ContentOrigin(kind="USER")
    with pytest.raises((ValidationError, TypeError)):
        origin.kind = "WEB"  # type: ignore


def test_source_record_valid_urls():
    rec1 = SourceRecord(
        source_id="src-1",
        url="https://example.com/report.pdf",
        title="Q3 Report",
    )
    assert rec1.url == "https://example.com/report.pdf"
    assert rec1.approved is False
    assert rec1.retrieved_at is not None

    rec2 = SourceRecord(
        source_id="src-2",
        url="http://sub.domain.org/data?query=1#section",
        title="Data Page",
        summary="Data overview",
        claims=["Claim A", "Claim B"],
        approved=True,
    )
    assert rec2.approved is True
    assert len(rec2.claims) == 2


def test_source_record_invalid_urls():
    with pytest.raises(ValueError, match="Invalid URL"):
        SourceRecord(
            source_id="src-bad-1",
            url="javascript:alert(1)",
            title="Malicious URL",
        )

    with pytest.raises(ValueError, match="Invalid URL"):
        SourceRecord(
            source_id="src-bad-2",
            url="file:///etc/passwd",
            title="Local file",
        )

    with pytest.raises(ValueError, match="Invalid URL"):
        SourceRecord(
            source_id="src-bad-3",
            url="not-a-valid-url",
            title="Invalid",
        )

    with pytest.raises(ValueError, match="Invalid URL"):
        SourceRecord(
            source_id="src-bad-4",
            url="ftp://ftp.example.com/file",
            title="FTP protocol",
        )


def test_source_record_immutable():
    rec = SourceRecord(
        source_id="src-1",
        url="https://example.com",
        title="Title",
    )
    with pytest.raises((ValidationError, TypeError)):
        rec.approved = True  # type: ignore


def test_research_result_model():
    rec = SourceRecord(
        source_id="src-1",
        url="https://example.com",
        title="Title",
    )
    res = ResearchResult(
        query="market share 2026",
        sources=[rec],
        summary="Market summary",
    )
    assert res.query == "market share 2026"
    assert len(res.sources) == 1
    assert res.summary == "Market summary"
    assert res.retrieved_at is not None


def test_generated_content_model():
    origin = ContentOrigin(kind="AI_GENERATED", runtime_name="codex")
    content = GeneratedContent(
        prompt="Write bullet points for slide 2",
        text="- Point 1\n- Point 2",
        origin=origin,
        model_or_runtime="codex",
    )
    assert content.origin.kind == "AI_GENERATED"
    assert content.origin.runtime_name == "codex"
    assert "- Point 1" in content.text


def test_provenance_record_model():
    origin = ContentOrigin(kind="WEB", source_ids=["src-10"])
    dest = TargetReference(slide_index=2, object_ref="TextBox 1")
    prov = ProvenanceRecord(
        content_ref="ref-block-1",
        origin=origin,
        destination=dest,
    )
    assert prov.content_ref == "ref-block-1"
    assert prov.origin.kind == "WEB"
    assert prov.destination.slide_index == 2
    assert prov.destination.object_ref == "TextBox 1"
    assert prov.created_at is not None
