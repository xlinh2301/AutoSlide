import pytest
from autoslide.planner.models import (
    TargetReference,
    TargetScope,
    TaskPlan,
    ReplaceTextOp,
)
from autoslide.conversation.models import SourceRecord
from autoslide.content.models import (
    ContentOrigin,
    ProvenanceRecord,
)
from autoslide.conversation.provenance import ProvenanceStore


def test_provenance_store_attach_and_get():
    store = ProvenanceStore()
    origin = ContentOrigin(kind="WEB", source_ids=["src-1"])
    dest = TargetReference(slide_index=1, object_ref="Title")

    record = store.attach(content_ref="block-1", origin=origin, destination=dest)
    assert record.content_ref == "block-1"
    assert record.origin.kind == "WEB"
    assert record.destination.slide_index == 1

    fetched = store.get("block-1")
    assert fetched is not None
    assert fetched.content_ref == "block-1"
    assert fetched.origin.source_ids == ["src-1"]

    assert store.get("non-existent") is None


def test_provenance_store_list_by_slide():
    store = ProvenanceStore()
    store.attach(
        content_ref="b-1",
        origin=ContentOrigin(kind="WEB", source_ids=["src-1"]),
        destination=TargetReference(slide_index=1, object_ref="Header"),
    )
    store.attach(
        content_ref="b-2",
        origin=ContentOrigin(kind="AI_GENERATED", runtime_name="gemini"),
        destination=TargetReference(slide_index=1, object_ref="Body"),
    )
    store.attach(
        content_ref="b-3",
        origin=ContentOrigin(kind="USER"),
        destination=TargetReference(slide_index=2, object_ref="Title"),
    )

    slide1_records = store.list_by_slide(1)
    assert len(slide1_records) == 2
    refs = {r.content_ref for r in slide1_records}
    assert refs == {"b-1", "b-2"}

    slide2_records = store.list_by_slide(2)
    assert len(slide2_records) == 1
    assert slide2_records[0].content_ref == "b-3"

    slide3_records = store.list_by_slide(3)
    assert slide3_records == []


def test_provenance_store_list_all_and_clear():
    store = ProvenanceStore()
    store.attach(
        content_ref="b-1",
        origin=ContentOrigin(kind="USER"),
        destination=TargetReference(slide_index=1),
    )
    assert len(store.list_all()) == 1

    store.clear()
    assert len(store.list_all()) == 0


def test_provenance_store_filter_approved_sources():
    sources = [
        SourceRecord(
            source_id="s1",
            url="https://example.com/1",
            title="S1",
            approved=True,
        ),
        SourceRecord(
            source_id="s2",
            url="https://example.com/2",
            title="S2",
            approved=False,
        ),
        SourceRecord(
            source_id="s3",
            url="https://example.com/3",
            title="S3",
            approved=True,
        ),
    ]

    approved = ProvenanceStore.filter_approved_sources(sources)
    assert len(approved) == 2
    assert [s.source_id for s in approved] == ["s1", "s3"]


def test_provenance_store_validate_plan_sources():
    store = ProvenanceStore()
    # Attach a web source to slide 1
    store.attach(
        content_ref="b-1",
        origin=ContentOrigin(kind="WEB", source_ids=["src-approved"]),
        destination=TargetReference(slide_index=1, object_ref="Box 1"),
    )
    # Attach an unapproved web source to slide 2
    store.attach(
        content_ref="b-2",
        origin=ContentOrigin(kind="WEB", source_ids=["src-rejected"]),
        destination=TargetReference(slide_index=2, object_ref="Box 2"),
    )

    plan_slide1 = TaskPlan(
        target_scope=[TargetScope(slide_index=1)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref="Box 1"),
                value="Approved text",
            )
        ],
    )

    plan_slide2 = TaskPlan(
        target_scope=[TargetScope(slide_index=2)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=2, object_ref="Box 2"),
                value="Unapproved text",
            )
        ],
    )

    approved_sources = [
        SourceRecord(
            source_id="src-approved",
            url="https://example.com/approved",
            title="Approved",
            approved=True,
        ),
        SourceRecord(
            source_id="src-rejected",
            url="https://example.com/rejected",
            title="Rejected",
            approved=False,
        ),
    ]

    # Plan 1 only references approved source -> Valid
    assert store.validate_plan_sources(plan_slide1, approved_sources) is True

    # Plan 2 references rejected source -> Invalid
    assert store.validate_plan_sources(plan_slide2, approved_sources) is False
