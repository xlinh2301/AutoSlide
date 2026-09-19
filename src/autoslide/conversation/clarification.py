"""ClarificationEngine for assessing edit requests, identifying missing fields, and generating questions."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from autoslide.conversation.models import ConversationState, EditBrief
from autoslide.ingest.models import DeckInventory
from autoslide.planner.models import TargetScope


class Question(BaseModel):
    """A targeted clarifying question asked by the assistant."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    options: list[str] | None = None
    field: Literal["target", "action", "content", "preservation"] | None = None


class ClarificationResult(BaseModel):
    """Result of evaluating a conversation message for completeness."""

    model_config = ConfigDict(frozen=True)

    state: ConversationState
    assistant_message: str
    questions: list[Question] = Field(default_factory=list)
    brief: EditBrief | None = None


class ClarificationEngine:
    """Deterministic assessment engine checking target, action, content, and preservation."""

    def assess(
        self,
        message: str,
        inventory: DeckInventory | None = None,
        previous_brief: EditBrief | None = None,
        context: Any = None,
    ) -> ClarificationResult:
        """Assess user request against deck inventory and prior brief context.

        Emits exactly one targeted question if any critical field is missing or vague.
        Never mutates presentations during assessment.
        """
        raw_message = message.strip()
        msg_lower = raw_message.lower()

        prev_slide: int | None = None
        prev_object: str | None = None
        prev_constraints: list[str] = []
        prev_goal = ""

        if previous_brief:
            prev_constraints = list(previous_brief.constraints)
            prev_goal = previous_brief.goal
            if previous_brief.target_scope:
                prev_slide = previous_brief.target_scope[0].slide_index
                prev_object = previous_brief.target_scope[0].object_ref

        # 1. Resolve Target Slide
        slide_index: int | None = None
        if context and getattr(context, "slide_index", None) is not None:
            slide_index = context.slide_index

        if slide_index is None:
            slide_match = re.search(r"\bslide\s*(?:#|number\s*)?(\d+)\b", raw_message, re.IGNORECASE)
            if slide_match:
                slide_index = int(slide_match.group(1))
            elif prev_slide is not None:
                slide_index = prev_slide
            elif inventory and inventory.slide_count == 1:
                slide_index = 1

        # Check for inventory slide boundaries
        if slide_index is not None and inventory and inventory.slide_count > 0:
            if not (1 <= slide_index <= inventory.slide_count):
                prompt = (
                    f"Slide {slide_index} does not exist in this deck. "
                    f"Please choose a slide between 1 and {inventory.slide_count}."
                )
                options = [f"Slide {i}" for i in range(1, inventory.slide_count + 1)]
                question = Question(prompt=prompt, options=options, field="target")
                brief = EditBrief(
                    goal=raw_message,
                    target_scope=[],
                    constraints=prev_constraints,
                    missing_fields=["target"],
                    complete=False,
                )
                return ClarificationResult(
                    state=ConversationState.NEEDS_CLARIFICATION,
                    assistant_message=question.prompt,
                    questions=[question],
                    brief=brief,
                )

        # If slide index is still missing
        if slide_index is None:
            max_slides = inventory.slide_count if inventory and inventory.slide_count > 0 else 3
            prompt = "Which slide would you like to edit?"
            options = [f"Slide {i}" for i in range(1, max_slides + 1)]
            question = Question(prompt=prompt, options=options, field="target")
            brief = EditBrief(
                goal=raw_message,
                target_scope=[],
                constraints=prev_constraints,
                missing_fields=["target"],
                complete=False,
            )
            return ClarificationResult(
                state=ConversationState.NEEDS_CLARIFICATION,
                assistant_message=question.prompt,
                questions=[question],
                brief=brief,
            )

        # Resolve Target Object reference
        object_ref = prev_object
        if context and getattr(context, "object_ref", None):
            object_ref = context.object_ref
        elif re.search(r"\btitle\b", raw_message, re.IGNORECASE):
            object_ref = "title"
        elif re.search(r"\bsubtitle\b", raw_message, re.IGNORECASE):
            object_ref = "subtitle"
        elif re.search(r"\b(?:shape|text|element|chart|table|image)\b", raw_message, re.IGNORECASE):
            match_obj = re.search(r"\b(shape|text|chart|table|image)\b", raw_message, re.IGNORECASE)
            if match_obj:
                object_ref = match_obj.group(1).lower()

        # 2. Resolve Action
        action: str | None = None
        if any(w in msg_lower for w in ["change", "replace", "update", "rename", "rewrite", "set", "new title", "new text"]):
            action = "replace_text"
        elif any(w in msg_lower for w in ["format", "bold", "italic", "font", "size", "color"]):
            action = "format_text"
        elif any(w in msg_lower for w in ["duplicate", "clone"]):
            action = "duplicate_slide"
        elif any(w in msg_lower for w in ["delete", "remove slide"]):
            action = "delete_slide"
        elif previous_brief and not previous_brief.complete and "action" not in previous_brief.missing_fields:
            action = "replace_text"

        # Check for vague intent without concrete action
        is_vague_request = any(
            vague in msg_lower
            for vague in [
                "make this look",
                "modernize",
                "clean up",
                "improve",
                "do something",
                "make it better",
                "fix this",
            ]
        )
        if action is None or (is_vague_request and "to" not in msg_lower and "set" not in msg_lower):
            prompt = f"What specific change would you like to make on slide {slide_index}?"
            options = ["Change text", "Update formatting", "Replace image", "Move or resize", "Delete slide"]
            question = Question(prompt=prompt, options=options, field="action")
            brief = EditBrief(
                goal=raw_message,
                target_scope=[TargetScope(slide_index=slide_index, object_ref=object_ref)],
                constraints=prev_constraints,
                missing_fields=["action"],
                complete=False,
            )
            return ClarificationResult(
                state=ConversationState.NEEDS_CLARIFICATION,
                assistant_message=question.prompt,
                questions=[question],
                brief=brief,
            )

        # 3. Resolve Content
        content: str | None = None
        # Extract quoted content
        quoted = re.findall(r'["\']([^"\']+)["\']|[“”]([^“”]+)[“”]', raw_message)
        if quoted:
            first_match = quoted[0]
            content = first_match[0] if first_match[0] else first_match[1]
        else:
            # Match "to ...", "with ...", "as ...", "title: ..."
            content_match = re.search(
                r'(?:to|with|as|set(?:\s+the)?\s+(?:title|text)?\s+to|change(?:\s+it)?\s+to)\s+([A-Za-z0-9\s,\.\-_]+?)(?:\s+while|\s+preserving|\.|$)',
                raw_message,
                re.IGNORECASE,
            )
            if content_match:
                extracted = content_match.group(1).strip().strip("'\"“”")
                # Exclude trivial non-content keywords
                if extracted and extracted.lower() not in ["it", "this", "title", "subtitle"]:
                    content = extracted

        # If action requires content (e.g. replace_text) but none was provided
        if action in ("replace_text", "replace_image", "format_text") and not content:
            target_desc = object_ref or "element"
            prompt = f"What should the new {target_desc} on slide {slide_index} be?"
            question = Question(prompt=prompt, field="content")
            brief = EditBrief(
                goal=raw_message,
                target_scope=[TargetScope(slide_index=slide_index, object_ref=object_ref)],
                constraints=prev_constraints,
                missing_fields=["content"],
                complete=False,
            )
            return ClarificationResult(
                state=ConversationState.NEEDS_CLARIFICATION,
                assistant_message=question.prompt,
                questions=[question],
                brief=brief,
            )

        # 4. Resolve Preservation Intent
        constraints = list(prev_constraints)
        if any(p in msg_lower for p in ["preserving formatting", "preserve style", "keep style", "keep format", "keep font"]):
            if "font_family" not in constraints:
                constraints.append("font_family")
            if "position" not in constraints:
                constraints.append("position")
        if not constraints:
            constraints = ["font_family", "position"]

        # 5. Synthesize complete EditBrief
        full_goal = f"{prev_goal} -> {raw_message}" if prev_goal and prev_goal != raw_message else raw_message
        if content and content not in full_goal:
            full_goal = f"{full_goal}: '{content}'"

        target_scope = [TargetScope(slide_index=slide_index, object_ref=object_ref or "title")]
        complete_brief = EditBrief(
            goal=full_goal,
            target_scope=target_scope,
            constraints=constraints,
            missing_fields=[],
            complete=True,
        )

        target_name = f"the {object_ref}" if object_ref else "content"
        assistant_message = (
            f"I have prepared an edit plan to {action.replace('_', ' ')} {target_name} "
            f"on slide {slide_index}. Please review and approve the plan."
        )

        return ClarificationResult(
            state=ConversationState.WAITING_PLAN_APPROVAL,
            assistant_message=assistant_message,
            questions=[],
            brief=complete_brief,
        )
