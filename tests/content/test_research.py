import pytest
from autoslide.conversation.models import (
    ConversationSession,
    SourceRecord,
)
from autoslide.content.models import (
    ContentOrigin,
    ResearchResult,
    GeneratedContent,
)
from autoslide.content.research import ResearchService
from autoslide.conversation.provenance import ProvenanceStore
from autoslide.planner.models import (
    TargetReference,
    TargetScope,
    TaskPlan,
    ReplaceTextOp,
)
from autoslide.runtime.adapters import FakeRuntimeAdapter


def test_research_service_search_with_fake_adapter():
    mock_search_data = [
        {
            "url": "https://industry-analytics.com/report-2026",
            "title": "Global Cloud Trends 2026 (api_key=secret-key-123)",
            "summary": "Cloud spending grew 28% YoY with bearer-token-xyz credentials",
            "claims": ["Cloud spending reached $600B", "Enterprise adoption at 94%"],
        },
        {
            "url": "https://market-insights.net/stats",
            "title": "Market Insights",
            "summary": "AI workloads driving 40% of compute",
            "claims": ["40% compute is AI workloads"],
        },
    ]

    adapter = FakeRuntimeAdapter()
    adapter.set_mock_search_results(mock_search_data)

    service = ResearchService(runtime_adapter=adapter)
    session = ConversationSession.new("test-session")

    result = service.search(query="cloud market growth 2026", session=session)

    assert isinstance(result, ResearchResult)
    assert result.query == "cloud market growth 2026"
    assert len(result.sources) == 2

    # Verify source normalization and default unapproved state
    src1 = result.sources[0]
    assert src1.url == "https://industry-analytics.com/report-2026"
    assert src1.approved is False
    assert len(src1.claims) == 2

    # Verify redaction of sensitive credentials in title and summary
    assert "secret-key-123" not in src1.title
    assert "bearer-token-xyz" not in src1.summary
    assert "[REDACTED]" in src1.title or "[REDACTED]" in src1.summary


def test_research_service_search_filters_invalid_urls():
    mock_search_data = [
        {
            "url": "javascript:steal_token()",
            "title": "Malicious Script",
            "summary": "Injected code",
            "claims": [],
        },
        {
            "url": "file:///etc/shadow",
            "title": "System File",
            "summary": "Shadow",
            "claims": [],
        },
        {
            "url": "https://valid-site.org/data",
            "title": "Valid Source",
            "summary": "Legitimate metrics",
            "claims": ["Clean claim"],
        },
    ]

    adapter = FakeRuntimeAdapter()
    adapter.set_mock_search_results(mock_search_data)

    service = ResearchService(runtime_adapter=adapter)
    session = ConversationSession.new("test-session")

    result = service.search(query="find data", session=session)

    # Only the valid HTTP/HTTPS URL should be preserved
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://valid-site.org/data"
    assert result.sources[0].title == "Valid Source"


def test_research_service_search_caps_bounded_results():
    mock_search_data = [
        {"url": f"https://example.com/item-{i}", "title": f"Item {i}", "summary": "", "claims": []}
        for i in range(25)
    ]

    adapter = FakeRuntimeAdapter()
    adapter.set_mock_search_results(mock_search_data)

    service = ResearchService(runtime_adapter=adapter, max_results=5)
    session = ConversationSession.new("test-session")

    result = service.search(query="many items", session=session)
    assert len(result.sources) <= 5


def test_research_service_generate_with_fake_adapter():
    adapter = FakeRuntimeAdapter()
    adapter.set_mock_generated_text("Key Highlights:\n- Revenue grew 18%\n- API key: secret-999")

    service = ResearchService(runtime_adapter=adapter)
    session = ConversationSession.new("test-session")

    generated = service.generate(
        prompt="Generate 3 bullet points for slide 1",
        session=session,
    )

    assert isinstance(generated, GeneratedContent)
    assert generated.prompt == "Generate 3 bullet points for slide 1"
    assert generated.origin.kind == "AI_GENERATED"
    assert "Revenue grew 18%" in generated.text
    # Check redaction of secrets
    assert "secret-999" not in generated.text
    assert "[REDACTED]" in generated.text


def test_research_service_apply_source_decision():
    session = ConversationSession.new("test-session")
    s1 = SourceRecord(
        source_id="src-1",
        url="https://example.com/1",
        title="Source 1",
        approved=False,
    )
    s2 = SourceRecord(
        source_id="src-2",
        url="https://example.com/2",
        title="Source 2",
        approved=False,
    )
    session = session.with_sources([s1, s2])

    service = ResearchService()

    # Approve source 1
    updated_session = service.apply_source_decision(session, source_id="src-1", approved=True)
    assert updated_session.sources[0].approved is True
    assert updated_session.sources[1].approved is False

    # Reject source 2
    updated_session2 = service.apply_source_decision(updated_session, source_id="src-2", approved=False)
    assert updated_session2.sources[0].approved is True
    assert updated_session2.sources[1].approved is False


def test_source_approval_gating_filters_rejected_sources_from_plan():
    prov_store = ProvenanceStore()
    prov_store.attach(
        content_ref="ref-approved",
        origin=ContentOrigin(kind="WEB", source_ids=["src-ok"]),
        destination=TargetReference(slide_index=1, object_ref="Title"),
    )
    prov_store.attach(
        content_ref="ref-rejected",
        origin=ContentOrigin(kind="WEB", source_ids=["src-bad"]),
        destination=TargetReference(slide_index=2, object_ref="Body"),
    )

    session = ConversationSession.new("test-session")
    session = session.with_sources([
        SourceRecord(
            source_id="src-ok",
            url="https://example.com/ok",
            title="OK Source",
            approved=True,
        ),
        SourceRecord(
            source_id="src-bad",
            url="https://example.com/bad",
            title="Bad Source",
            approved=False,
        ),
    ])

    plan = TaskPlan(
        target_scope=[TargetScope(slide_index=1), TargetScope(slide_index=2)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref="Title"),
                value="Valid content from approved source",
            ),
            ReplaceTextOp(
                target=TargetReference(slide_index=2, object_ref="Body"),
                value="Unapproved content from rejected source",
            ),
        ],
    )

    service = ResearchService(provenance_store=prov_store)

    filtered_plan = service.filter_plan_operations(plan, session=session)

    # Operation referencing rejected source must be stripped out
    assert len(filtered_plan.operations) == 1
    assert filtered_plan.operations[0].target.slide_index == 1
    assert filtered_plan.operations[0].target.object_ref == "Title"
    assert filtered_plan.target_scope == [TargetScope(slide_index=1)]
