"""Structural before/after diff computation engine for auditing presentation mutations."""

from __future__ import annotations

from autoslide.executor.models import (
    PropertyChange,
    ShapeDiff,
    SlideDiff,
    StructuralDiff,
)
from autoslide.ingest.models import DeckInventory, ShapeInventoryItem
from autoslide.planner.models import TaskPlan


class StructuralDiffEngine:
    """Computes machine-readable structural diffs between pre- and post-execution DeckInventories."""

    def compute_diff(
        self,
        inventory_before: DeckInventory,
        inventory_after: DeckInventory,
        plan: TaskPlan,
    ) -> StructuralDiff:
        intended_changes: list[PropertyChange] = []
        unintended_changes: list[PropertyChange] = []
        slide_diffs: list[SlideDiff] = []

        # Map target scopes for classification
        scoped_targets: set[tuple[int, str | None]] = {
            (s.slide_index, s.object_ref) for s in plan.target_scope
        }
        scoped_slides: set[int] = {s.slide_index for s in plan.target_scope}

        slides_before = {s.slide_index: s for s in inventory_before.slides}
        slides_after = {s.slide_index: s for s in inventory_after.slides}

        all_slide_indices = sorted(set(slides_before.keys()) | set(slides_after.keys()))

        for s_idx in all_slide_indices:
            s_before = slides_before.get(s_idx)
            s_after = slides_after.get(s_idx)

            if s_before is None and s_after is not None:
                # Slide added
                slide_diffs.append(SlideDiff(slide_index=s_idx, status="added"))
                change = PropertyChange(
                    slide_index=s_idx,
                    shape_name="Slide",
                    property_name="slide_added",
                    old_value=None,
                    new_value=s_after.slide_path,
                )
                if s_idx in scoped_slides or any(op.op.value in ("duplicate_slide", "add_slide") for op in plan.operations):
                    intended_changes.append(change)
                else:
                    unintended_changes.append(change)
                continue

            if s_before is not None and s_after is None:
                # Slide deleted
                slide_diffs.append(SlideDiff(slide_index=s_idx, status="deleted"))
                change = PropertyChange(
                    slide_index=s_idx,
                    shape_name="Slide",
                    property_name="slide_deleted",
                    old_value=s_before.slide_path,
                    new_value=None,
                )
                if s_idx in scoped_slides or any(op.op.value == "delete_slide" for op in plan.operations):
                    intended_changes.append(change)
                else:
                    unintended_changes.append(change)
                continue

            # Compare shapes on existing slide (including nested group children)
            def _collect_shapes(items: list[ShapeInventoryItem]) -> dict[str, ShapeInventoryItem]:
                res: dict[str, ShapeInventoryItem] = {}
                for sh in items:
                    key = sh.shape_id or sh.shape_name
                    res[key] = sh
                    if sh.children:
                        for child_key, child_sh in _collect_shapes(sh.children).items():
                            res[child_key] = child_sh
                return res

            shapes_before = _collect_shapes(s_before.shapes)
            shapes_after = _collect_shapes(s_after.shapes)
            shape_diff_items: list[ShapeDiff] = []

            for key, shape_b in shapes_before.items():
                shape_a = shapes_after.get(key)
                if shape_a is None:
                    continue

                if shape_b.fingerprint != shape_a.fingerprint:
                    prop_changes: list[PropertyChange] = []

                    # 1. Text difference
                    if shape_b.raw_text != shape_a.raw_text:
                        prop_changes.append(
                            PropertyChange(
                                slide_index=s_idx,
                                shape_name=shape_b.shape_name,
                                object_ref=shape_b.fingerprint,
                                property_name="text",
                                old_value=shape_b.raw_text,
                                new_value=shape_a.raw_text,
                            )
                        )

                    # 2. Geometry difference
                    if (
                        shape_b.bounds.x != shape_a.bounds.x
                        or shape_b.bounds.y != shape_a.bounds.y
                        or shape_b.bounds.cx != shape_a.bounds.cx
                        or shape_b.bounds.cy != shape_a.bounds.cy
                    ):
                        prop_changes.append(
                            PropertyChange(
                                slide_index=s_idx,
                                shape_name=shape_b.shape_name,
                                object_ref=shape_b.fingerprint,
                                property_name="bounds",
                                old_value=shape_b.bounds.model_dump(),
                                new_value=shape_a.bounds.model_dump(),
                            )
                        )

                    # 3. Formatting difference
                    if shape_b.text_runs != shape_a.text_runs and shape_b.raw_text == shape_a.raw_text:
                        prop_changes.append(
                            PropertyChange(
                                slide_index=s_idx,
                                shape_name=shape_b.shape_name,
                                object_ref=shape_b.fingerprint,
                                property_name="formatting",
                                old_value=[r.model_dump() for r in shape_b.text_runs],
                                new_value=[r.model_dump() for r in shape_a.text_runs],
                            )
                        )

                    if not prop_changes:
                        # Fingerprint changed due to sub-attribute
                        prop_changes.append(
                            PropertyChange(
                                slide_index=s_idx,
                                shape_name=shape_b.shape_name,
                                object_ref=shape_b.fingerprint,
                                property_name="properties",
                                old_value=shape_b.fingerprint,
                                new_value=shape_a.fingerprint,
                            )
                        )

                    shape_diff_items.append(
                        ShapeDiff(
                            slide_index=s_idx,
                            shape_name=shape_b.shape_name,
                            old_fingerprint=shape_b.fingerprint,
                            new_fingerprint=shape_a.fingerprint,
                            changes=prop_changes,
                        )
                    )

                    # Classify intended vs unintended
                    is_in_scope = (
                        (s_idx, shape_b.fingerprint) in scoped_targets
                        or (s_idx, None) in scoped_targets
                    )
                    for pc in prop_changes:
                        if is_in_scope:
                            intended_changes.append(pc)
                        else:
                            unintended_changes.append(pc)

            slide_diffs.append(
                SlideDiff(
                    slide_index=s_idx,
                    status="modified" if shape_diff_items else "unchanged",
                    shape_diffs=shape_diff_items,
                )
            )

        return StructuralDiff(
            slide_count_before=inventory_before.slide_count,
            slide_count_after=inventory_after.slide_count,
            intended_changes=intended_changes,
            unintended_changes=unintended_changes,
            slide_diffs=slide_diffs,
        )
