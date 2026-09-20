"""Unit tests for Real Local Agent Engine."""

from __future__ import annotations

from pathlib import Path
import pytest

from autoslide.agent.engine import AgentEngine
from autoslide.agent.tools import ToolExecutionContext, ToolRegistry
from autoslide.conversation.models import ConversationSession, ConversationState
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx


@pytest.fixture
def agent_engine_setup(tmp_path: Path) -> tuple[AgentEngine, ConversationSession, ToolExecutionContext]:
    working_dir = tmp_path / "working"
    working_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = working_dir / "presentation.pptx"
    pptx_path.write_bytes(create_complex_multi_slide_pptx())

    session = ConversationSession.new(session_id="session_engine_test", job_id="job_engine_test")
    context = ToolExecutionContext(
        session_id="session_engine_test",
        job_id="job_engine_test",
        working_pptx_path=pptx_path,
    )
    engine = AgentEngine()
    return engine, session, context


def test_agent_engine_persona_and_init():
    """Verify system persona and initialization of AgentEngine."""
    engine = AgentEngine()
    assert "expert AI presentation architect" in engine.SYSTEM_PERSONA
    assert engine.tool_registry is not None


def test_agent_engine_edit_text_intent(agent_engine_setup):
    """Test agent processes edit text request and returns modified slide indices."""
    engine, session, context = agent_engine_setup
    user_msg = "Sửa tiêu đề slide 1 thành 'Tổng Quan Kết Quả Kinh Doanh Q3'"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert response.session_id == session.session_id
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "edit_slide_text"
    assert response.modified_slide_indices == [1]
    assert "Tổng Quan Kết Quả Kinh Doanh Q3" in response.assistant_message


def test_agent_engine_add_slide_intent(agent_engine_setup):
    """Test agent processes add slide request."""
    engine, session, context = agent_engine_setup
    user_msg = "Thêm slide mới với tiêu đề 'Chiến Lược Mở Rộng 2027'"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "add_slide"
    assert len(response.modified_slide_indices) == 1
    assert "Chiến Lược Mở Rộng 2027" in response.assistant_message


def test_agent_engine_delete_slide_intent(agent_engine_setup):
    """Test agent processes delete slide request."""
    engine, session, context = agent_engine_setup
    user_msg = "Xóa slide 2"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "delete_slide"
    assert response.modified_slide_indices == [2]
    assert "xóa slide 2" in response.assistant_message.lower()


def test_agent_engine_reorder_slide_intent(agent_engine_setup):
    """Test agent processes reorder slide request."""
    engine, session, context = agent_engine_setup
    user_msg = "Chuyển slide 1 sang slide 3"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "reorder_slide"
    assert response.modified_slide_indices == [1, 3]


def test_agent_engine_update_style_intent(agent_engine_setup):
    """Test agent processes theme style change request."""
    engine, session, context = agent_engine_setup
    user_msg = "Đổi theme slide 1 thành modern_dark"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "update_slide_style"
    assert response.modified_slide_indices == [1]


def test_agent_engine_analysis_intent(agent_engine_setup):
    """Test agent processes calculation and analysis request."""
    engine, session, context = agent_engine_setup
    user_msg = "Hãy phân tích và tính tổng các số liệu trên slide"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "analyze_slide_content"
    assert response.modified_slide_indices == []
    assert "Kết quả phân tích" in response.assistant_message


def test_agent_engine_search_intent(agent_engine_setup):
    """Test agent processes web search request."""
    engine, session, context = agent_engine_setup
    user_msg = "Tìm kiếm về xu hướng AI trong năm 2026"

    response = engine.process_message(session=session, message=user_msg, context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "search_web"
    assert response.modified_slide_indices == []


def test_agent_engine_conversational_fallback(agent_engine_setup):
    """Test agent responds naturally to greetings and help queries without calling tools."""
    engine, session, context = agent_engine_setup

    # Greeting
    resp_greet = engine.process_message(session=session, message="Xin chào bạn", context=context)
    assert len(resp_greet.tool_calls) == 0
    assert "AutoSlide Agent" in resp_greet.assistant_message

    # Help
    resp_help = engine.process_message(session=session, message="Bạn có thể giúp gì cho tôi?", context=context)
    assert len(resp_help.tool_calls) == 0
    assert "chỉnh sửa" in resp_help.assistant_message or "slide" in resp_help.assistant_message
