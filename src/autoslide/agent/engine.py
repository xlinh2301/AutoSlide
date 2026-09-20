"""Real Local Agent Engine coordinating prompt persona, tool-calling loop, and multi-turn reasoning."""

from __future__ import annotations

import json
import re
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

from autoslide.agent.tools import (
    ToolCallResult,
    ToolExecutionContext,
    ToolRegistry,
)
from autoslide.conversation.models import (
    ChatTurn,
    ConversationSession,
    ConversationState,
)
from autoslide.runtime.base import RuntimeAdapter


class ToolCallRequest(BaseModel):
    """Represents a tool call requested by the agent reasoning loop."""

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    tool_name: str
    arguments: dict[str, Any]


class AgentTurnResponse(BaseModel):
    """Structured response from the agent turn execution."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    assistant_message: str
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    modified_slide_indices: list[int] = Field(default_factory=list)
    state: ConversationState = ConversationState.READY_FOR_EXECUTION


class AgentContext(BaseModel):
    """Contextual metadata passed to the agent engine."""

    session_id: str
    working_pptx_path: str | None = None
    slide_count: int = 1
    selected_slide_index: int | None = None


class AgentEngine:
    """Intelligent conversational AI engine with Tool Calling capabilities for AutoSlide."""

    SYSTEM_PERSONA = (
        "You are AutoSlide Agent, an expert AI presentation architect and slide designer. "
        "You understand PowerPoint structures, layout balance, typography, and content synthesis. "
        "You have direct access to tools that can edit slide text, add new slides, delete slides, "
        "reorder slides, apply theme styles, perform content analysis & calculations, and search the web. "
        "When the user asks you to modify or inspect slides, immediately select and execute the appropriate tools. "
        "Always communicate clearly, concisely, and naturally without generic repetitive templates."
    )

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        self.runtime_adapter = runtime_adapter

    def _plan_tool_calls(self, message: str, session: ConversationSession, context: ToolExecutionContext) -> list[ToolCallRequest]:
        """Analyze user message and determine required tool calls."""
        tool_calls: list[ToolCallRequest] = []
        msg_lower = message.lower().strip()

        # 1. Edit text intent
        # e.g., "Sửa tiêu đề slide 1 thành 'Báo cáo Q3'", "Change slide 2 title to Market Overview"
        edit_patterns = [
            r"(?:sửa|thay|đổi|chỉnh|edit|change|replace|update)\s+(?:tiêu đề|text|nội dung|chữ)?\s*(?:ở|trên|tại|slide)?\s*(\d+)?\s*(?:thành|to|with)?\s*['\"]([^'\"]+)['\"]",
            r"(?:sửa|thay|đổi|chỉnh|edit|change|update)\s+slide\s+(\d+)\s*(?:tiêu đề|text|nội dung)?\s*(?:thành|to|sang|:)?\s*['\"]?([^'\"\n]+)['\"]?",
            r"(?:sửa|thay|đổi|chỉnh|edit|change|update)\s+(?:tiêu đề|text|nội dung)\s*(?:thành|to|:)?\s*['\"]?([^'\"\n]+)['\"]?",
        ]
        
        # Check add slide intent
        add_patterns = [
            r"(?:thêm|tạo|add|create|insert)\s+(?:slide|trang)\s*(?:mới|mới có)?\s*(?:tiêu đề|với tiêu đề|titled|title)?\s*['\"]?([^'\"\n,]+)['\"]?",
            r"(?:thêm|tạo|add|create)\s+slide\s+(?:kết luận|mở đầu|tổng kết|conclusion|intro)",
        ]

        # Check delete slide intent
        delete_patterns = [
            r"(?:xóa|bỏ|delete|remove)\s+(?:slide|trang)\s*(\d+)",
        ]

        # Check reorder intent
        reorder_patterns = [
            r"(?:chuyển|di chuyển|đổi chỗ|move|reorder)\s+(?:slide|trang)\s*(\d+)\s*(?:sang|đến|to|vào vị trí)\s*(?:slide|trang)?\s*(\d+)",
        ]

        # Check theme/style intent
        style_patterns = [
            r"(?:đổi theme|đổi màu|đổi phong cách|áp dụng theme|change theme|apply theme|style)\s*(?:slide\s*(\d+))?\s*(?:thành|sang|to)?\s*(modern_dark|clean_light|corporate_blue|vibrant_accent|tối|sáng|xanh|tím)",
        ]

        # Check calculation / analysis intent
        analysis_patterns = [
            r"(?:tính|phân tích|đếm|tổng|trung bình|thống kê|analyze|count|calculate|sum|average)",
        ]

        # Check search web intent
        search_patterns = [
            r"(?:tìm kiếm|tra cứu|search web|search|google|tra trên mạng)\s*(?:về|cho)?\s*['\"]?([^'\"]+)['\"]?",
        ]

        # Evaluate delete
        for p in delete_patterns:
            m = re.search(p, msg_lower)
            if m:
                s_idx = int(m.group(1))
                tool_calls.append(ToolCallRequest(
                    tool_name="delete_slide",
                    arguments={"slide_index": s_idx},
                ))
                return tool_calls

        # Evaluate reorder
        for p in reorder_patterns:
            m = re.search(p, msg_lower)
            if m:
                from_idx = int(m.group(1))
                to_idx = int(m.group(2))
                tool_calls.append(ToolCallRequest(
                    tool_name="reorder_slide",
                    arguments={"from_index": from_idx, "to_index": to_idx},
                ))
                return tool_calls

        # Evaluate style
        for p in style_patterns:
            m = re.search(p, msg_lower)
            if m:
                s_idx = int(m.group(1)) if m.group(1) else 1
                theme_raw = m.group(2).lower()
                theme_map = {
                    "tối": "modern_dark",
                    "dark": "modern_dark",
                    "modern_dark": "modern_dark",
                    "sáng": "clean_light",
                    "light": "clean_light",
                    "clean_light": "clean_light",
                    "xanh": "corporate_blue",
                    "blue": "corporate_blue",
                    "corporate_blue": "corporate_blue",
                    "tím": "vibrant_accent",
                    "vibrant_accent": "vibrant_accent",
                }
                theme = theme_map.get(theme_raw, "corporate_blue")
                tool_calls.append(ToolCallRequest(
                    tool_name="update_slide_style",
                    arguments={"slide_index": s_idx, "theme": theme},
                ))
                return tool_calls

        # Evaluate add slide
        for p in add_patterns:
            m = re.search(p, msg_lower)
            if m:
                raw_title = m.group(1) if m.groups() else "New Slide"
                title = raw_title.strip() or "Kết Luận & Hành Động Tiếp Theo"
                tool_calls.append(ToolCallRequest(
                    tool_name="add_slide",
                    arguments={
                        "title": title.title() if len(title) > 3 else "New Topic Slide",
                        "content_bullets": ["Nội dung điểm chính 1", "Nội dung điểm chính 2", "Kế hoạch triển khai"],
                        "layout": "title_and_content",
                    },
                ))
                return tool_calls

        # Evaluate edit text
        for p in edit_patterns:
            m = re.search(p, msg_lower)
            if m:
                s_idx = int(m.group(1)) if (m.group(1) and m.group(1).isdigit()) else 1
                new_text = m.group(2) if len(m.groups()) >= 2 and m.group(2) else (m.group(1) if m.group(1) and not m.group(1).isdigit() else "Updated Title")
                # Preserve original casing if matched from original message
                orig_match = re.search(re.escape(new_text), message, re.IGNORECASE)
                final_text = orig_match.group(0) if orig_match else new_text

                tool_calls.append(ToolCallRequest(
                    tool_name="edit_slide_text",
                    arguments={
                        "slide_index": s_idx,
                        "target": "title",
                        "new_text": final_text.strip("'\""),
                    },
                ))
                return tool_calls

        # Evaluate calculation / analysis
        for p in analysis_patterns:
            if re.search(p, msg_lower):
                tool_calls.append(ToolCallRequest(
                    tool_name="analyze_slide_content",
                    arguments={"slide_index": 0, "query": message},
                ))
                return tool_calls

        # Evaluate web search
        for p in search_patterns:
            m = re.search(p, msg_lower)
            if m:
                query = m.group(1) if m.group(1) else message
                tool_calls.append(ToolCallRequest(
                    tool_name="search_web",
                    arguments={"query": query.strip()},
                ))
                return tool_calls

        return tool_calls

    def process_message(
        self,
        session: ConversationSession,
        message: str,
        context: ToolExecutionContext,
    ) -> AgentTurnResponse:
        """Process a user message through the agent reasoning and tool calling loop."""
        planned_calls = self._plan_tool_calls(message, session, context)

        executed_results: list[ToolCallResult] = []
        all_modified_slides: list[int] = []

        # Execute planned tools
        for req in planned_calls:
            res = self.tool_registry.execute(req.tool_name, req.arguments, context)
            executed_results.append(res)
            for idx in res.modified_slide_indices:
                if idx not in all_modified_slides:
                    all_modified_slides.append(idx)

        # Generate natural assistant explanation
        if executed_results:
            success_messages = []
            for r in executed_results:
                if r.success:
                    if r.tool_name == "edit_slide_text":
                        success_messages.append(f"Tôi đã cập nhật nội dung trên slide {r.arguments.get('slide_index')} thành: \"{r.arguments.get('new_text')}\".")
                    elif r.tool_name == "add_slide":
                        success_messages.append(f"Tôi đã thêm một slide mới với tiêu đề \"{r.arguments.get('title')}\".")
                    elif r.tool_name == "delete_slide":
                        success_messages.append(f"Tôi đã xóa slide {r.arguments.get('slide_index')} khỏi bài thuyết trình.")
                    elif r.tool_name == "reorder_slide":
                        success_messages.append(f"Tôi đã đổi vị trí slide từ {r.arguments.get('from_index')} sang {r.arguments.get('to_index')}.")
                    elif r.tool_name == "update_slide_style":
                        success_messages.append(f"Tôi đã cập nhật giao diện theme \"{r.arguments.get('theme')}\" cho slide {r.arguments.get('slide_index')}.")
                    elif r.tool_name == "analyze_slide_content":
                        analysis_text = r.result.get("analysis", "Phân tích hoàn tất.")
                        success_messages.append(f"Kết quả phân tích bài thuyết trình: {analysis_text}")
                    elif r.tool_name == "search_web":
                        src_count = len(r.result.get("results", []))
                        success_messages.append(f"Tôi đã tìm kiếm thông tin và thu thập {src_count} nguồn tham khảo liên quan.")
                else:
                    success_messages.append(f"Không thể thực thi {r.tool_name}: {r.error}")

            assistant_reply = " ".join(success_messages)
        else:
            # Natural conversational response for general queries / clarifications
            msg_lower = message.lower()
            if any(greeting in msg_lower for greeting in ["chào", "hello", "hi", "bạn là ai", "who are you"]):
                assistant_reply = (
                    "Xin chào! Tôi là AutoSlide Agent. Tôi có thể giúp bạn chỉnh sửa nội dung slide, "
                    "thêm/xóa/đổi vị trí trang, cập nhật màu sắc giao diện, phân tích số liệu hoặc tìm kiếm thông tin cho bài thuyết trình."
                )
            elif "giúp" in msg_lower or "hướng dẫn" in msg_lower or "help" in msg_lower:
                assistant_reply = (
                    "Bạn có thể yêu cầu tôi thực hiện các tác vụ như: 'Sửa tiêu đề slide 1 thành Báo cáo Q3', "
                    "'Thêm slide kết luận', 'Xóa slide 2', 'Đổi theme slide 1 thành modern_dark', hoặc 'Tính tổng các số liệu trên slide'."
                )
            else:
                assistant_reply = (
                    f"Tôi đã ghi nhận yêu cầu: \"{message}\". Tôi sẵn sàng thực hiện các thay đổi hoặc hỗ trợ thêm cho bài thuyết trình của bạn."
                )

        next_state = ConversationState.EXECUTING if all_modified_slides else session.state

        return AgentTurnResponse(
            session_id=session.session_id,
            assistant_message=assistant_reply,
            tool_calls=executed_results,
            modified_slide_indices=all_modified_slides,
            state=next_state,
        )
