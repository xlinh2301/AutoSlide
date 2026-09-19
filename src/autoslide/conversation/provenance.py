"""ProvenanceStore tracking origin attribution, destination links, and source approval gating."""

from __future__ import annotations

from typing import Iterable, Set, Union
from autoslide.content.models import ContentOrigin, ProvenanceRecord, SourceRecord
from autoslide.planner.models import TargetReference, TaskPlan


class ProvenanceStore:
    """Session-scoped store tracking provenance graph and gating unapproved sources."""

    def __init__(self, records: list[ProvenanceRecord] | None = None) -> None:
        self._records: dict[str, ProvenanceRecord] = {}
        if records:
            for r in records:
                self._records[r.content_ref] = r

    def attach(
        self,
        content_ref: str,
        origin: ContentOrigin,
        destination: TargetReference,
    ) -> ProvenanceRecord:
        """Record provenance origin and slide destination mapping."""
        record = ProvenanceRecord(
            content_ref=content_ref,
            origin=origin,
            destination=destination,
        )
        self._records[content_ref] = record
        return record

    def get(self, content_ref: str) -> ProvenanceRecord | None:
        """Lookup provenance record by content reference."""
        return self._records.get(content_ref)

    def list_by_slide(self, slide_index: int) -> list[ProvenanceRecord]:
        """Retrieve all provenance records targeting a specific slide."""
        return [
            r for r in self._records.values()
            if r.destination.slide_index == slide_index
        ]

    def list_all(self) -> list[ProvenanceRecord]:
        """Return all recorded provenance links."""
        return list(self._records.values())

    def clear(self) -> None:
        """Clear all stored provenance records."""
        self._records.clear()

    @staticmethod
    def filter_approved_sources(sources: Iterable[SourceRecord]) -> list[SourceRecord]:
        """Filter source records returning only explicitly approved ones."""
        return [s for s in sources if s.approved]

    def validate_plan_sources(
        self,
        plan: TaskPlan,
        approved_sources: Union[Iterable[SourceRecord], Set[str]],
    ) -> bool:
        """Check if all provenance records associated with the plan target approved sources.

        Args:
            plan: The TaskPlan to validate.
            approved_sources: Iterable of SourceRecords or set of approved source_ids.

        Returns:
            True if all web sources referenced by the plan targets are approved; False otherwise.
        """
        approved_ids: set[str] = set()
        for item in approved_sources:
            if hasattr(item, "source_id"):
                if getattr(item, "approved", True):
                    approved_ids.add(getattr(item, "source_id"))
            elif isinstance(item, str):
                approved_ids.add(item)

        # Identify all slide indices targeted in the plan
        target_slide_indices = {s.slide_index for s in plan.target_scope}
        for op in plan.operations:
            target = getattr(op, "target", None)
            if target and hasattr(target, "slide_index"):
                target_slide_indices.add(target.slide_index)
            slide_idx = getattr(op, "slide_index", None)
            if slide_idx is not None:
                target_slide_indices.add(slide_idx)
            source_idx = getattr(op, "source_slide_index", None)
            if source_idx is not None:
                target_slide_indices.add(source_idx)

        # Check all provenance records matching targeted slides
        for record in self._records.values():
            if record.destination.slide_index in target_slide_indices:
                if record.origin.kind == "WEB":
                    for s_id in record.origin.source_ids:
                        if s_id not in approved_ids:
                            return False

        return True
