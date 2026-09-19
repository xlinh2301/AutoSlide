from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import uuid

from autoslide.content.models import (
    ContentOrigin,
    GeneratedContent,
    ResearchResult,
    SourceRecord,
)
from autoslide.events import Redactor
from autoslide.runtime.adapters import AntigravityAdapter
from autoslide.runtime.base import RuntimeAdapter

if TYPE_CHECKING:
    from autoslide.conversation.models import ConversationSession
    from autoslide.conversation.provenance import ProvenanceStore
    from autoslide.planner.models import TargetScope, TaskPlan


class ResearchService:
    """Coordinates search, generation, source validation, and approval gating."""

    def __init__(
        self,
        runtime_adapter: RuntimeAdapter | None = None,
        provenance_store: ProvenanceStore | None = None,
        max_results: int = 10,
    ) -> None:
        self.runtime_adapter = runtime_adapter or AntigravityAdapter()
        if provenance_store is not None:
            self.provenance_store = provenance_store
        else:
            from autoslide.conversation.provenance import ProvenanceStore
            self.provenance_store = ProvenanceStore()
        self.max_results = max_results

    def search(
        self,
        query: str,
        session: ConversationSession | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
    ) -> ResearchResult:
        """Perform web search via runtime adapter, sanitize output, and return normalized SourceRecords."""
        adapter = runtime_adapter or self.runtime_adapter
        raw_items: list[dict[str, Any]] = []

        if hasattr(adapter, "run_search"):
            raw_items = adapter.run_search(query)

        sources: list[SourceRecord] = []
        for item in raw_items:
            if len(sources) >= self.max_results:
                break
            raw_url = item.get("url", "")
            raw_title = item.get("title", "")
            raw_summary = item.get("summary", "")
            raw_claims = item.get("claims", [])

            # Redact credentials and sensitive data
            safe_title = Redactor.redact(str(raw_title))
            safe_summary = Redactor.redact(str(raw_summary))
            safe_claims = [Redactor.redact(str(c)) for c in raw_claims]

            source_id = item.get("source_id") or f"src-{uuid.uuid4().hex[:8]}"

            try:
                record = SourceRecord(
                    source_id=source_id,
                    url=raw_url,
                    title=safe_title,
                    summary=safe_summary,
                    claims=safe_claims,
                    approved=False,
                )
                sources.append(record)
            except (ValueError, Exception):
                # Filter out malformed or non-http(s) URLs safely
                continue

        summary = f"Found {len(sources)} sources for query '{query}'"
        return ResearchResult(
            query=query,
            sources=sources,
            summary=summary,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def generate(
        self,
        prompt: str,
        session: ConversationSession | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
    ) -> GeneratedContent:
        """Generate content via runtime adapter with explicit AI_GENERATED origin attribution."""
        adapter = runtime_adapter or self.runtime_adapter
        raw_text = ""

        if hasattr(adapter, "run_generate"):
            raw_text = adapter.run_generate(prompt)
        elif hasattr(adapter, "start"):
            raw_text = ""

        safe_text = Redactor.redact(raw_text)
        runtime_name = getattr(adapter, "name", None)

        origin = ContentOrigin(
            kind="AI_GENERATED",
            source_ids=[],
            runtime_name=runtime_name,
        )

        return GeneratedContent(
            prompt=prompt,
            text=safe_text,
            origin=origin,
            model_or_runtime=runtime_name,
        )

    def apply_source_decision(
        self,
        session: ConversationSession,
        source_id: str,
        approved: bool,
    ) -> ConversationSession:
        """Update approval state of a specific SourceRecord in the session."""
        updated_sources: list[SourceRecord] = []
        for s in session.sources:
            if s.source_id == source_id:
                updated_sources.append(
                    SourceRecord(
                        source_id=s.source_id,
                        url=s.url,
                        title=s.title,
                        retrieved_at=s.retrieved_at,
                        summary=s.summary,
                        claims=s.claims,
                        approved=approved,
                    )
                )
            else:
                updated_sources.append(s)

        return session.with_sources(updated_sources)

    def filter_plan_operations(
        self,
        plan: TaskPlan,
        session: ConversationSession,
        provenance_store: ProvenanceStore | None = None,
    ) -> TaskPlan:
        """Filter out operations targeting slides linked to unapproved web sources."""
        store = provenance_store or self.provenance_store
        approved_source_ids = {s.source_id for s in session.sources if s.approved}

        valid_operations = []
        for op in plan.operations:
            slide_idx: int | None = None
            target = getattr(op, "target", None)
            if target and hasattr(target, "slide_index"):
                slide_idx = target.slide_index
            elif hasattr(op, "slide_index"):
                slide_idx = getattr(op, "slide_index")
            elif hasattr(op, "source_slide_index"):
                slide_idx = getattr(op, "source_slide_index")

            if slide_idx is not None:
                slide_provs = store.list_by_slide(slide_idx)
                has_unapproved_source = False
                for prov in slide_provs:
                    if prov.origin.kind == "WEB":
                        for sid in prov.origin.source_ids:
                            if sid not in approved_source_ids:
                                has_unapproved_source = True
                                break
                    if has_unapproved_source:
                        break

                if has_unapproved_source:
                    # Skip operation because it relies on an unapproved source
                    continue

            valid_operations.append(op)

        # Update target_scope to include only remaining valid slide indices
        remaining_slides = set()
        for op in valid_operations:
            target = getattr(op, "target", None)
            if target and hasattr(target, "slide_index"):
                remaining_slides.add(target.slide_index)
            elif hasattr(op, "slide_index"):
                remaining_slides.add(getattr(op, "slide_index"))
            elif hasattr(op, "source_slide_index"):
                remaining_slides.add(getattr(op, "source_slide_index"))

        new_target_scope = [
            ts for ts in plan.target_scope
            if ts.slide_index in remaining_slides
        ]

        return plan.model_copy(
            update={
                "operations": valid_operations,
                "target_scope": new_target_scope,
            }
        )
