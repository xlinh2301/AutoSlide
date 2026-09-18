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
