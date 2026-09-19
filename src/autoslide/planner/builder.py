"""Prompt payload construction for local agent CLI runtimes without provider API keys."""

from __future__ import annotations

import json
from typing import Any

from autoslide.ingest.models import DeckInventory
from autoslide.planner.models import TaskPlan

SYSTEM_PLANNING_PROMPT = """You are the AutoSlide Edit Planner.
Your job is to analyze the user's natural-language presentation editing request and the provided slide inventory, then produce a strictly typed JSON TaskPlan conforming to schema version 1.0.

Guidelines:
1. ONLY use allowlisted operations: 'replace_text', 'format_text', 'replace_image', 'move_resize_shape', 'duplicate_slide', 'delete_slide'.
2. Reference shapes using their exact stable composite 'fingerprint' from the inventory in 'object_ref'.
3. Declare the full 'target_scope' of slides and objects permissible to modify.
4. Specify preservation rules for unmutated properties (e.g., 'font_family', 'position', 'theme_color').
5. Assign a realistic confidence score (0.0 to 1.0). If the instruction is ambiguous or confidence < 0.80, set 'requires_review': true.
6. Return ONLY valid JSON conforming to the schema. Do NOT emit markdown formatting, commentary, or executable code scripts."""


class PromptPayloadBuilder:
    """Builds token-efficient, secret-free prompt payloads for agent CLI runtimes."""

    def __init__(self, system_prompt: str = SYSTEM_PLANNING_PROMPT):
        self.system_prompt = system_prompt

    def build_payload(
        self,
        user_instruction: str,
        inventory: DeckInventory,
        custom_guidelines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compile user instruction, inventory, and schema into a structured prompt dictionary."""
        compact_inventory = self.format_compact_inventory(inventory)

        user_prompt_lines = [
            f"User Edit Instruction: {user_instruction.strip()}",
            "",
            "Presentation Deck Inventory:",
            compact_inventory,
        ]

        if custom_guidelines:
            user_prompt_lines.append("")
            user_prompt_lines.append("Additional Preservation Guidelines:")
            for g in custom_guidelines:
                user_prompt_lines.append(f"- {g}")

        user_prompt_lines.append("")
        user_prompt_lines.append("Emit the JSON TaskPlan:")

        return {
            "system_prompt": self.system_prompt,
            "user_prompt": "\n".join(user_prompt_lines),
            "schema": TaskPlan.model_json_schema(),
        }

    def format_compact_inventory(self, inventory: DeckInventory) -> str:
        """Format a compact, token-efficient summary of deck shapes and fingerprints."""
        lines: list[str] = [
            f"Deck Summary: {inventory.slide_count} slides (dimensions: {inventory.dimensions.cx}x{inventory.dimensions.cy} EMU)"
        ]

        for slide in inventory.slides:
            lines.append(f"\nSlide {slide.slide_index} (id: {slide.slide_id}, path: {slide.slide_path}):")
            if not slide.shapes:
                lines.append("  (No shapes found on slide)")
                continue

            for shape in slide.shapes:
                ph_info = f", placeholder: {shape.placeholder_type}" if shape.placeholder_type else ""
                text_preview = f' | text: "{shape.raw_text}"' if shape.raw_text else ""
                lines.append(
                    f"  - Shape '{shape.shape_name}' [type: {shape.shape_type}{ph_info}]"
                    f" | fp: {shape.fingerprint}{text_preview}"
                )

                if shape.table_data:
                    lines.append(f"    Table data: {shape.table_data}")

                if shape.children:
                    for child in shape.children:
                        c_text = f' | text: "{child.raw_text}"' if child.raw_text else ""
                        lines.append(
                            f"    * Nested '{child.shape_name}' [type: {child.shape_type}]"
                            f" | fp: {child.fingerprint}{c_text}"
                        )

        return "\n".join(lines)

    def build_plan_from_brief(
        self,
        brief: Any,
        inventory: DeckInventory | None = None,
    ) -> TaskPlan:
        """Construct a strongly typed TaskPlan from a completed EditBrief."""
        from autoslide.planner.models import (
            DeleteSlideOp,
            DuplicateSlideOp,
            ReplaceTextOp,
            TargetReference,
            TargetScope,
        )

        slide_index = 1
        object_ref: str | None = None
        if brief.target_scope:
            slide_index = brief.target_scope[0].slide_index
            object_ref = brief.target_scope[0].object_ref

        # Look up shape fingerprint in inventory if available
        resolved_fp = object_ref
        if inventory:
            target_slide = next((s for s in inventory.slides if s.slide_index == slide_index), None)
            if target_slide and target_slide.shapes:
                if object_ref and object_ref.lower() in ("title", "subtitle"):
                    matched_shape = next(
                        (
                            sh
                            for sh in target_slide.shapes
                            if (sh.placeholder_type and object_ref.lower() in sh.placeholder_type.lower())
                            or (sh.shape_name and object_ref.lower() in sh.shape_name.lower())
                            or (sh.shape_type and object_ref.lower() in sh.shape_type.lower())
                        ),
                        target_slide.shapes[0],
                    )
                    resolved_fp = matched_shape.fingerprint
                elif not object_ref:
                    resolved_fp = target_slide.shapes[0].fingerprint

        if not resolved_fp:
            resolved_fp = f"fp-slide{slide_index}-title"

        preserve = list(brief.constraints) if brief.constraints else ["font_family", "position"]
        goal_lower = brief.goal.lower()
        operations = []

        if "delete" in goal_lower and "slide" in goal_lower:
            operations.append(DeleteSlideOp(slide_index=slide_index, preserve=preserve))
        elif "duplicate" in goal_lower:
            operations.append(
                DuplicateSlideOp(
                    source_slide_index=slide_index,
                    insert_at_index=slide_index + 1,
                    preserve=preserve,
                )
            )
        else:
            # Extract replacement text value from brief.goal
            import re

            quoted = re.findall(r'["\']([^"\']+)["\']|[“”]([^“”]+)[“”]', brief.goal)
            if quoted:
                first = quoted[-1]
                value = first[0] if first[0] else first[1]
            else:
                value = brief.goal

            operations.append(
                ReplaceTextOp(
                    target=TargetReference(slide_index=slide_index, object_ref=resolved_fp),
                    value=value,
                    preserve=preserve,
                )
            )

        target_scope = [TargetScope(slide_index=slide_index, object_ref=resolved_fp)]

        return TaskPlan(
            schema_version="1.0",
            target_scope=target_scope,
            operations=operations,
            requires_review=False,
            rationale=brief.goal,
        )

