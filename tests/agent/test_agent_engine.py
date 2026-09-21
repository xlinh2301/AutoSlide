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


def test_agent_engine_slide_qa_intent(agent_engine_setup):
    """Test agent identifies questions about slide content and outputs analysis directly."""
    engine, session, context = agent_engine_setup

    queries = [
        ("slide 1 có gì", 1),
        ("nội dung slide 1", 1),
        ("tóm tắt slide 2", 2),
        ("trên slide 1 có những gì", 1),
    ]

    for q, expected_idx in queries:
        resp = engine.process_message(session=session, message=q, context=context)
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool_name == "analyze_slide_content"
        assert resp.tool_calls[0].arguments["slide_index"] == expected_idx
        assert f"Nội dung trên Slide {expected_idx} bao gồm:" in resp.assistant_message
        assert "Tôi đã ghi nhận yêu cầu" not in resp.assistant_message


def test_agent_engine_natural_language_edit_intents(agent_engine_setup):
    """Test flexible natural language edit commands with conversational particles."""
    engine, session, context = agent_engine_setup

    test_cases = [
        ("sửa lại title slide 1 là ABC đi", 1, "ABC"),
        ("sửa lại title slide 1 là ABC", 1, "ABC"),
        ("sửa title slide 1 là ABC đi", 1, "ABC"),
        ("đổi tiêu đề slide 1 thành ABC", 1, "ABC"),
        ("sửa slide 1 thành ABC", 1, "ABC"),
        ("thay title slide 1 bằng ABC", 1, "ABC"),
        ("sửa lại tiêu đề slide 1 thành Báo cáo Kết quả", 1, "Báo cáo Kết quả"),
    ]

    for msg, expected_slide, expected_text in test_cases:
        resp = engine.process_message(session=session, message=msg, context=context)
        assert len(resp.tool_calls) == 1, f"Failed for message: {msg}"
        call = resp.tool_calls[0]
        assert call.tool_name == "edit_slide_text"
        assert call.arguments["slide_index"] == expected_slide
        assert call.arguments["new_text"] == expected_text
        assert "Tôi đã cập nhật nội dung trên slide" in resp.assistant_message


def test_agent_engine_consecutive_confirmation_memory(agent_engine_setup):
    """Test that follow-up confirmation 'sửa đi' triggers previously proposed edit from history."""
    engine, session, context = agent_engine_setup
    from autoslide.conversation.models import ChatTurn

    # Simulate prior user turn requesting title change
    prior_turn = ChatTurn(id="turn_prev_1", role="user", content="sửa lại title slide 1 là ABC đi")
    session_with_history = session.with_turn(prior_turn)

    # Now user says "sửa đi" or "ok sửa đi"
    for confirm_msg in ["sửa đi", "ok sửa đi", "làm đi"]:
        resp = engine.process_message(session=session_with_history, message=confirm_msg, context=context)
        assert len(resp.tool_calls) == 1, f"Failed on confirm: {confirm_msg}"
        assert resp.tool_calls[0].tool_name == "edit_slide_text"
        assert resp.tool_calls[0].arguments["slide_index"] == 1
        assert resp.tool_calls[0].arguments["new_text"] == "ABC"


def test_agent_engine_beautify_custom_intent(agent_engine_setup):
    """Test custom / beautify commands route to update_slide_style."""
    engine, session, context = agent_engine_setup

    for msg, expected_slide in [("custom sao cho đẹp tí", 1), ("làm đẹp slide 2", 2), ("sao cũng đc", 1), ("sửa cho đẹp hơn", 1), ("sửa slide 2 cho đẹp hơn", 2)]:
        resp = engine.process_message(session=session, message=msg, context=context)
        assert len(resp.tool_calls) == 1, f"Failed on: {msg}"
        assert resp.tool_calls[0].tool_name == "update_slide_style"
        assert resp.tool_calls[0].arguments["slide_index"] == expected_slide


def test_agent_engine_multi_turn_sua_slide_1_dep_hon_sua_di(agent_engine_setup):
    """Test exact user interaction: 'sửa slide 1' -> 'sửa cho đẹp hơn' -> 'sửa đi'."""
    engine, session, context = agent_engine_setup
    from autoslide.conversation.models import ChatTurn

    # Turn 1: user says "sửa slide 1"
    resp1 = engine.process_message(session=session, message="sửa slide 1", context=context)
    assert len(resp1.tool_calls) == 0
    assert "Slide 1" in resp1.assistant_message
    session = session.with_turn(ChatTurn(id="t1", role="user", content="sửa slide 1"))
    session = session.with_turn(ChatTurn(id="t2", role="assistant", content=resp1.assistant_message))

    # Turn 2: user says "sửa cho đẹp hơn" -> should inherit Slide 1 and run update_slide_style
    resp2 = engine.process_message(session=session, message="sửa cho đẹp hơn", context=context)
    assert len(resp2.tool_calls) == 1
    assert resp2.tool_calls[0].tool_name == "update_slide_style"
    assert resp2.tool_calls[0].arguments["slide_index"] == 1
    session = session.with_turn(ChatTurn(id="t3", role="user", content="sửa cho đẹp hơn"))
    session = session.with_turn(ChatTurn(id="t4", role="assistant", content=resp2.assistant_message))

    # Turn 3: user says "sửa đi" -> should re-execute or confirm update_slide_style on Slide 1
    resp3 = engine.process_message(session=session, message="sửa đi", context=context)
    assert len(resp3.tool_calls) == 1
    assert resp3.tool_calls[0].tool_name == "update_slide_style"
    assert resp3.tool_calls[0].arguments["slide_index"] == 1


