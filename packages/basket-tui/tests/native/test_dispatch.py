"""Tests for native dispatch per-type handlers."""

from basket_tui.native.handle.dispatch import (
    handle_agent_aborted,
    handle_agent_complete,
    handle_agent_error,
    handle_agent_switched,
    handle_session_switched,
    handle_text_delta,
    handle_thinking_delta,
    handle_todo_update,
    handle_tool_call_end,
    handle_tool_call_start,
)
from basket_tui.native.pipeline import StreamAssembler


def _minimal_setup():
    """Minimal args: assembler, width, output_put, last_output_count."""
    assembler = StreamAssembler()
    width = 80
    out: list[str] = []
    output_put = out.append
    last_output_count: list[int] = [0]
    return assembler, width, out, output_put, last_output_count


def test_handle_text_delta_updates_assembler_buffer():
    assembler, *_ = _minimal_setup()
    handle_text_delta(assembler, "hi")
    assert assembler._buffer == "hi"


def test_handle_text_delta_sets_ui_state_phase_streaming():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_text_delta(assembler, "x", ui_state=ui_state)
    assert ui_state["phase"] == "streaming"


def test_handle_thinking_delta_updates_assembler():
    assembler, *_ = _minimal_setup()
    handle_thinking_delta(assembler, "think")
    assert assembler._thinking_buffer == "think"


def test_handle_tool_call_start_sets_current_tool():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "ls"})
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "bash"
    assert assembler._current_tool["arguments"] == {"cmd": "ls"}


def test_handle_tool_call_start_sets_ui_state_phase_tool_running():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_tool_call_start(assembler, "bash", arguments={}, ui_state=ui_state)
    assert ui_state["phase"] == "tool_running"


def test_handle_tool_call_end_appends_tool_message():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "read", arguments={})
    handle_tool_call_end(assembler, "read", result="file content", error=None)
    tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "read" in tool_msgs[0]["content"]
    assert "file content" in tool_msgs[0]["content"]


def test_handle_tool_call_end_with_error():
    assembler, *_ = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_tool_call_end(assembler, "bash", result=None, error="failed")
    tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "error" in tool_msgs[0]["content"] or "failed" in tool_msgs[0]["content"]


def test_handle_agent_complete_commits_and_renders():
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_text_delta(assembler, "Hi")
    handle_agent_complete(assembler, width, output_put, last_output_count)
    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "assistant"
    assert assembler.messages[0]["content"] == "Hi"
    assert last_output_count[0] == 1
    assert len(out) >= 1


def test_handle_agent_complete_sets_ui_state_phase_idle():
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_text_delta(assembler, "x", ui_state=ui_state)
    handle_agent_complete(assembler, width, output_put, last_output_count, ui_state=ui_state)
    assert ui_state["phase"] == "idle"


def test_handle_agent_error_prints_message():
    _, _, out, output_put, _ = _minimal_setup()
    handle_agent_error(output_put, "Something failed")
    assert len(out) == 1
    assert "Something failed" in out[0]
    assert "[system]" in out[0] or "Agent error" in out[0]


def test_handle_agent_error_sets_ui_state_phase_error():
    assembler, *_ = _minimal_setup()
    ui_state: dict[str, str] = {}
    handle_agent_error(lambda _: None, "err", ui_state=ui_state)
    assert ui_state["phase"] == "error"


def test_handle_session_switched_updates_header_and_output():
    header_state: dict[str, str] = {}
    out: list[str] = []
    output_put = out.append
    handle_session_switched(header_state, output_put, "s1")
    assert header_state["session"] == "s1"
    assert len(out) == 1
    assert "s1" in out[0]


def test_handle_session_switched_empty_sid_no_update():
    header_state: dict[str, str] = {"session": "old"}
    out: list[str] = []
    output_put = out.append
    handle_session_switched(header_state, output_put, "")
    assert header_state["session"] == "old"
    assert len(out) == 0


def test_handle_session_switched_none_header_state():
    out: list[str] = []
    output_put = out.append
    handle_session_switched(None, output_put, "s2")
    assert len(out) == 1
    assert "s2" in out[0]


def test_handle_agent_switched_updates_header_and_output():
    header_state: dict[str, str] = {}
    out: list[str] = []
    output_put = out.append
    handle_agent_switched(header_state, output_put, "explore")
    assert header_state["agent"] == "explore"
    assert len(out) == 1
    assert "explore" in out[0]


def test_handle_agent_switched_empty_name_no_update():
    header_state: dict[str, str] = {"agent": "old"}
    out: list[str] = []
    output_put = out.append
    handle_agent_switched(header_state, output_put, "")
    assert header_state["agent"] == "old"
    assert len(out) == 0


def test_handle_agent_aborted_clears_assembler_and_prints():
    assembler, _, out, output_put, _ = _minimal_setup()
    handle_text_delta(assembler, "x")
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_agent_aborted(assembler, output_put)
    assert assembler._buffer == ""
    assert assembler._thinking_buffer == ""
    assert assembler._current_tool is None
    assert any("Aborted" in line for line in out)


def test_handle_tool_call_start_flushes_buffer_and_renders():
    """When buffer has content, tool_call_start flushes it as assistant msg and renders via output_put."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    # Simulate prior streaming
    assembler.text_delta("I'll read the file")
    assert assembler._buffer == "I'll read the file"

    handle_tool_call_start(
        assembler,
        "read",
        arguments={"path": "/etc/hosts"},
        ui_state={"phase": "streaming"},
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # Buffer should be flushed: assistant message committed
    assert assembler._buffer == ""
    assert any(m["role"] == "assistant" and m["content"] == "I'll read the file" for m in assembler.messages)
    # Tool should be recorded
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "read"
    # Output should contain rendered assistant text
    assert len(out) >= 1
    # last_output_count should track the flushed assistant message
    assert last_output_count[0] >= 1


def test_handle_tool_call_start_empty_buffer_no_flush():
    """When buffer is empty, tool_call_start does not add assistant message."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()

    handle_tool_call_start(
        assembler,
        "bash",
        arguments={},
        ui_state={"phase": "idle"},
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # No assistant message added
    assistant_msgs = [m for m in assembler.messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 0
    # Tool recorded
    assert assembler._current_tool is not None
    assert assembler._current_tool["tool_name"] == "bash"


def test_handle_tool_call_end_renders_immediately():
    """tool_call_end renders tool block via output_put immediately (not waiting for agent_complete)."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "echo hi"})
    handle_tool_call_end(
        assembler,
        "bash",
        result="hello",
        error=None,
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    # Tool message in assembler
    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "tool"
    # Rendered immediately via output_put
    assert len(out) >= 1
    # last_output_count tracks the rendered tool message
    assert last_output_count[0] == 1


def test_handle_tool_call_end_error_renders_immediately():
    """tool_call_end with error renders error tool block via output_put immediately."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={})
    handle_tool_call_end(
        assembler,
        "bash",
        result=None,
        error="command not found",
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )

    assert len(assembler.messages) == 1
    assert assembler.messages[0]["role"] == "tool"
    assert len(out) >= 1
    assert last_output_count[0] == 1


def test_consecutive_tool_blocks_have_spacing_between_them():
    """Two consecutive tool blocks rendered via handle_tool_call_end must have blank-line spacing."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()

    # First tool call
    handle_tool_call_start(assembler, "read", arguments={"path": "/a"})
    handle_tool_call_end(
        assembler, "read", result="content-a", error=None,
        width=width, output_put=output_put, last_output_count=last_output_count,
    )

    # Second tool call
    handle_tool_call_start(assembler, "write", arguments={"path": "/b"})
    handle_tool_call_end(
        assembler, "write", result="ok", error=None,
        width=width, output_put=output_put, last_output_count=last_output_count,
    )

    # There must be at least one empty line between the two tool blocks
    joined = "\n".join(out)
    idx_content_a = joined.find("content-a")
    idx_write = joined.find("write", idx_content_a + 1 if idx_content_a >= 0 else 0)
    assert idx_content_a >= 0, "First tool result must appear in output"
    assert idx_write > idx_content_a, "Second tool must appear after first"
    between = joined[idx_content_a:idx_write]
    assert "\n\n" in between, (
        f"Expected blank line between consecutive tool blocks, got: {between!r}"
    )


def test_handle_todo_update_stores_todos():
    """handle_todo_update stores the todo list snapshot."""
    todo_state: list[dict] = []
    todos = [
        {"id": "1", "content": "Task A", "status": "pending"},
        {"id": "2", "content": "Task B", "status": "in_progress"},
    ]
    handle_todo_update(todo_state, todos)
    assert len(todo_state) == 2
    assert todo_state[0]["content"] == "Task A"
    assert todo_state[1]["status"] == "in_progress"


def test_handle_todo_update_replaces_previous():
    """handle_todo_update replaces previous state (snapshot semantics)."""
    todo_state: list[dict] = [{"id": "old", "content": "Old", "status": "completed"}]
    handle_todo_update(todo_state, [{"id": "new", "content": "New", "status": "pending"}])
    assert len(todo_state) == 1
    assert todo_state[0]["id"] == "new"


def test_handle_todo_update_empty_clears_state():
    """handle_todo_update with empty list clears state."""
    todo_state: list[dict] = [{"id": "1", "content": "X", "status": "pending"}]
    handle_todo_update(todo_state, [])
    assert len(todo_state) == 0


# --- Tool message suppression ---

_SUPPRESSED_TOOLS = ("ask_user_question", "todo_write")


def test_handle_tool_call_start_suppressed_tool_no_render():
    """ask_user_question tool_call_start records tool but does not render to output."""
    for tool_name in _SUPPRESSED_TOOLS:
        assembler, width, out, output_put, last_output_count = _minimal_setup()
        assembler.text_delta("Some text")
        handle_tool_call_start(
            assembler,
            tool_name,
            arguments={"q": "test"},
            ui_state={"phase": "streaming"},
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
        # Tool recorded in assembler
        assert assembler._current_tool is not None
        assert assembler._current_tool["tool_name"] == tool_name
        # Buffer NOT flushed to output (no render of prior text for suppressed tool)
        assert len(out) == 0, f"{tool_name}: suppressed tool should not render"


def test_handle_tool_call_end_suppressed_tool_no_render():
    """ask_user_question/todo_write tool_call_end records message but does not render."""
    for tool_name in _SUPPRESSED_TOOLS:
        assembler, width, out, output_put, last_output_count = _minimal_setup()
        handle_tool_call_start(assembler, tool_name, arguments={})
        handle_tool_call_end(
            assembler,
            tool_name,
            result="ok",
            error=None,
            width=width,
            output_put=output_put,
            last_output_count=last_output_count,
        )
        # Tool message recorded in assembler
        tool_msgs = [m for m in assembler.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        # NOT rendered to output
        assert len(out) == 0, f"{tool_name}: suppressed tool should not render"


def test_handle_tool_call_end_normal_tool_still_renders():
    """Normal tools (e.g. 'bash') still render to output."""
    assembler, width, out, output_put, last_output_count = _minimal_setup()
    handle_tool_call_start(assembler, "bash", arguments={"cmd": "ls"})
    handle_tool_call_end(
        assembler,
        "bash",
        result="file.txt",
        error=None,
        width=width,
        output_put=output_put,
        last_output_count=last_output_count,
    )
    assert len(out) >= 1, "Normal tool should render"
