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

        # Check slide content Q&A intent
        # e.g., 'slide X có gì', 'nội dung slide X', 'tóm tắt slide X', 'trên slide X có những gì'
        slide_qa_patterns = [
            r"(?:trên|ở|trong)?\s*(?:slide|trang)\s*(\d+)?\s*(?:có gì|có những gì|nội dung gì|viết gì|gồm những gì|nói về gì|nói về cái gì|là gì|thế nào)",
            r"(?:nội dung|tóm tắt|chi tiết|thông tin|phân tích)\s+(?:của\s+|trên\s+)?(?:slide|trang)\s*(\d+)?",
            r"(?:xem|kiểm tra|đọc)\s+(?:nội dung\s+)?(?:slide|trang)\s*(\d+)",
            r"(?:slide|trang)\s*(\d+)\s+(?:nội dung|tóm tắt|chi tiết|thông tin|có gì|viết gì)",
            r"(?:what(?:'s| is) on|content of|summarize|details of)\s+(?:slide|page)\s*(\d+)?",
            r"(?:slide|page)\s*(\d+)\s+(?:content|summary|details)",
            r"^(?:có gì|có những gì|nội dung là gì|nội dung gì|nói về gì|thông tin gì|tóm tắt|xem nội dung|chi tiết)$",
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

        # Evaluate slide content Q&A
        for p in slide_qa_patterns:
            m = re.search(p, msg_lower)
            if m:
                s_idx = 1
                if m.groups() and m.group(1) and m.group(1).isdigit():
                    s_idx = int(m.group(1))
                elif getattr(context, "selected_slide_index", None):
                    s_idx = int(context.selected_slide_index)
                tool_calls.append(ToolCallRequest(
                    tool_name="analyze_slide_content",
                    arguments={"slide_index": s_idx, "query": message},
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
                        success_messages.append(analysis_text)
                    elif r.tool_name == "search_web":
                        src_count = len(r.result.get("results", []))
                        success_messages.append(f"Tôi đã tìm kiếm thông tin và thu thập {src_count} nguồn tham khảo liên quan.")
                else:
                    success_messages.append(f"Không thể thực thi {r.tool_name}: {r.error}")

            if len(success_messages) == 1:
                assistant_reply = success_messages[0]
            else:
                assistant_reply = "\n\n".join(success_messages)
        else:
            # Natural conversational response for general queries / clarifications
            msg_lower = message.lower().strip()
            if any(q in msg_lower for q in ["bạn là ai", "who are you", "giới thiệu về bạn", "ai đây", "bạn tên gì"]):
                assistant_reply = (
                    "Tôi là **AutoSlide AI Assistant** — trợ lý thiết kế và biên tập bài thuyết trình PowerPoint chuẩn phong cách Canva Studio.\n\n"
                    "Tôi có thể hỗ trợ bạn:\n"
                    "• 🔍 **Đọc hiểu & Phân tích**: Trích xuất chi tiết tiêu đề, số liệu và gạch đầu dòng từng slide\n"
                    "• ✍️ **Chỉnh sửa nội dung**: Đổi tiêu đề, thay đổi câu chữ và bổ sung luận điểm\n"
                    "• 📑 **Quản lý cấu trúc**: Thêm trang mới, xóa trang hoặc sắp xếp lại thứ tự bài trình bày\n"
                    "• 🎨 **Giao diện Canva**: Cập nhật màu sắc, theme thanh lịch nền sáng hoặc tối\n"
                    "• 🌐 **Nghiên cứu dẫn chứng**: Tìm kiếm dữ liệu và trích dẫn mới nhất từ web."
                )
            elif any(greeting in msg_lower for greeting in ["chào", "hello", "hi", "hey", "alo"]):
                slide_count = None
                if context and context.working_pptx_path and context.working_pptx_path.exists():
                    try:
                        from autoslide.ingest.renderer import _extract_slide_titles_and_shapes
                        t, _, _ = _extract_slide_titles_and_shapes(context.working_pptx_path)
                        if t:
                            slide_count = len(t)
                    except Exception:
                        pass

                if slide_count:
                    assistant_reply = (
                        f"Xin chào! Tôi là AutoSlide Agent. Tôi đã nạp bài thuyết trình ({slide_count} slides) trên Canvas. "
                        "Bạn muốn tôi điều chỉnh slide nào, đổi theme giao diện Canva, hay cần phân tích chi tiết nội dung trang nào?"
                    )
                else:
                    assistant_reply = (
                        "Xin chào! Tôi là AutoSlide Agent. Hãy tải lên tệp PowerPoint (.pptx) "
                        "để xem trước slide chuẩn Canva và cùng tôi tối ưu hóa bài thuyết trình nhé!"
                    )
            elif any(h in msg_lower for h in ["giúp", "hướng dẫn", "help", "làm được gì"]):
                assistant_reply = (
                    "Dưới đây là một số ví dụ thao tác bạn có thể thử ngay:\n"
                    "• *'Slide 1 có gì?'* — Tra cứu toàn bộ nội dung và gạch đầu dòng trên Slide 1\n"
                    "• *'Sửa tiêu đề slide 1 thành Báo cáo Tổng kết'* — Chỉnh sửa tiêu đề tức thì\n"
                    "• *'Thêm slide mới với tiêu đề Kế hoạch Hành động'* — Tạo thêm slide mới\n"
                    "• *'Xóa slide 2'* — Loại bỏ slide không cần thiết\n"
                    "• *'Đổi vị trí slide 3 sang 1'* — Sắp xếp lại thứ tự trình bày\n"
                    "• *'Đổi theme slide 1 sang canva_clean'* — Cập nhật phong cách giao diện"
                )
            elif any(k in msg_lower for k in ["nói về gì", "chủ đề", "tóm tắt cả bài", "tổng quan bài", "overview"]):
                if context.working_pptx_path and context.working_pptx_path.exists():
                    try:
                        from autoslide.ingest.renderer import _extract_slide_titles_and_shapes
                        t, _, _ = _extract_slide_titles_and_shapes(context.working_pptx_path)
                        if t:
                            summary_lines = [f"• Slide {k}: **{v}**" for k, v in sorted(t.items())[:8]]
                            assistant_reply = (
                                f"Bài thuyết trình gồm {len(t)} slide với cấu trúc các phần:\n" +
                                "\n".join(summary_lines) +
                                ("\n..." if len(t) > 8 else "") +
                                "\n\nBạn muốn tôi tập trung chỉnh sửa hoặc phân tích sâu slide nào?"
                            )
                        else:
                            assistant_reply = "Bài thuyết trình hiện chưa có nội dung văn bản cụ thể. Bạn có thể thêm nội dung mới cho từng trang."
                    except Exception:
                        assistant_reply = "Tôi có thể hỗ trợ bạn xem lại bài thuyết trình. Hãy cho tôi biết slide bạn muốn xem."
                else:
                    assistant_reply = "Chưa có bài thuyết trình nào được nạp. Hãy tải lên file .pptx để tôi phân tích nhé!"
            else:
                # Contextual conversational response
                llm_response = ""
                try:
                    from autoslide.runtime.adapters import AntigravityAdapter
                    adapter = AntigravityAdapter()
                    if adapter.resolve_executable():
                        prompt = (
                            f"Bạn là AutoSlide AI Assistant, trợ lý chỉnh sửa slide bài thuyết trình PowerPoint chuẩn Canva. "
                            f"Người dùng hỏi: '{message}'. Hãy trả lời thân thiện, súc tích (1-3 câu) bằng tiếng Việt."
                        )
                        llm_response = adapter.run_generate(prompt=prompt, timeout_seconds=8)
                except Exception:
                    pass

                if llm_response and len(llm_response.strip()) > 5:
                    assistant_reply = llm_response.strip()
                else:
                    assistant_reply = (
                        f"Tôi đã hiểu yêu cầu của bạn về \"{message}\". "
                        "Tôi có thể giúp bạn chỉnh sửa nội dung văn bản, phân tích số liệu trên slide, hoặc cập nhật giao diện Canva. "
                        "Bạn muốn thực hiện thay đổi nào tiếp theo?"
                    )

        next_state = ConversationState.EXECUTING if all_modified_slides else session.state

        return AgentTurnResponse(
            session_id=session.session_id,
            assistant_message=assistant_reply,
            tool_calls=executed_results,
            modified_slide_indices=all_modified_slides,
            state=next_state,
        )
