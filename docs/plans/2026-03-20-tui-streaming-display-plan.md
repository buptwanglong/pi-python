# TUI 流式展示（方案一）Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 native TUI 中实现大模型回复的流式展示：流式阶段纯文本打字机效果，agent_complete 后整段以 Markdown 定格。

**Architecture:** body_lines 仅存已落盘内容；流式时通过 get_body_lines() 返回 body_lines + stream_preview_lines(assembler._buffer, width)；layout 消费 get_body_lines；handle_text_delta 后调用 on_streaming_update() 触发重绘。详见 `docs/plans/2026-03-20-tui-streaming-display-design.md`。

**Tech Stack:** prompt_toolkit, basket_tui native (run.py, layout.py, pipeline/render.py, handle/dispatch.py, handle/handlers.py), pytest.

---

## Task 1: stream_preview_lines 与单测

**Design ref:** §3 组件职责 — pipeline/render.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/pipeline/render.py`
- Test: `packages/basket-tui/tests/native/test_render.py`（若无则新建）

**Step 1: Write the failing test**

在 `packages/basket-tui/tests/native/test_render.py` 中新增（或创建文件并加入）：

```python
from basket_tui.native.pipeline.render import stream_preview_lines

def test_stream_preview_lines_empty_returns_empty_list():
    assert stream_preview_lines("", 80) == []

def test_stream_preview_lines_short_line_one_line():
    assert stream_preview_lines("hello", 80) == ["hello"]

def test_stream_preview_lines_long_line_wraps():
    text = "a" * 100
    lines = stream_preview_lines(text, 40)
    assert len(lines) >= 3
    assert all(len(ln) <= 40 for ln in lines)
    assert "".join(lines).replace("\n", "") == text.replace("\n", "")

def test_stream_preview_lines_preserves_newlines():
    text = "line1\nline2"
    lines = stream_preview_lines(text, 80)
    assert "line1" in lines[0]
    assert "line2" in lines[-1] or "line2" in lines[1]
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v -k stream_preview`
Expected: FAIL (e.g. stream_preview_lines not defined)

**Step 3: Write minimal implementation**

在 `packages/basket-tui/basket_tui/native/pipeline/render.py` 顶部增加 `import textwrap`，在 `render_messages` 之前增加：

```python
def stream_preview_lines(text: str, width: int) -> list[str]:
    """Plain-text wrap for streaming preview; no Markdown. Returns [] for empty text."""
    if not text or width <= 0:
        return []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        for wline in textwrap.wrap(paragraph, width=width):
            lines.append(wline)
    return lines
```

**Step 4: Run test to verify it passes**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v -k stream_preview`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/pipeline/render.py packages/basket-tui/tests/native/test_render.py
git commit -m "feat(basket-tui): add stream_preview_lines for streaming overlay"
```

---

## Task 2: layout 改为使用 get_body_lines

**Design ref:** §3 组件职责 — ui/layout.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/layout.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: Change layout signature and body control**

在 `packages/basket-tui/basket_tui/native/ui/layout.py` 中：
- 将 `body_lines: list[str]` 改为 `get_body_lines: Callable[[], list[str]]`。
- 将 body 的 `text=lambda: ANSI("\n".join(body_lines))` 改为 `text=lambda: ANSI("\n".join(get_body_lines()))`。
- Debug 日志中 `body_lines_count` 改为 `len(get_body_lines())`。
- 在文件顶部 `from collections.abc import Callable` 已存在则保留；确保类型注解使用 `Callable[[], list[str]]`。

**Step 2: Run existing tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: 可能有失败，因为 run.py 仍传 body_lines。下一步修改 run.py。

**Step 3: run.py 定义 get_body_lines 并传入 layout**

在 `packages/basket-tui/basket_tui/native/run.py` 中：
- 在 `build_layout` 调用之前定义：
  - `from ..pipeline.render import render_messages, stream_preview_lines`（若尚未导入 stream_preview_lines 则加上）。
  - `def get_body_lines() -> list[str]: base = list(body_lines); ...` 若 `ui_state.get("phase") == "streaming"` 且 `assembler._buffer` 则 `base.extend(stream_preview_lines(assembler._buffer, width))`；`return base`。
- 将 `build_layout(..., body_lines, ...)` 改为 `build_layout(..., get_body_lines, ...)`（参数名若在 layout 中为 get_body_lines 则传 get_body_lines）。

**Step 4: _body_line_count 使用 get_body_lines**

在 run.py 中把 `_body_line_count` 改为基于 get_body_lines：例如 `raw = "\n".join(get_body_lines()); return len(raw.split("\n")) if raw else 0`。

**Step 5: Run tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: PASS（若有 layout 相关单测需同步改为传 callable）。

**Step 6: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/layout.py packages/basket-tui/basket_tui/native/run.py
git commit -m "refactor(basket-tui): layout uses get_body_lines for streaming overlay"
```

---

## Task 3: handle_text_delta 触发重绘（on_streaming_update）

**Design ref:** §3 组件职责 — handle/dispatch.py, handle/handlers.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/handle/dispatch.py`
- Modify: `packages/basket-tui/basket_tui/native/handle/handlers.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: handle_text_delta 增加 on_streaming_update**

在 `packages/basket-tui/basket_tui/native/handle/dispatch.py` 中：
- `handle_text_delta` 签名增加 `on_streaming_update: Optional[Callable[[], None]] = None`。
- 在 `assembler.text_delta(delta)` 及 ui_state 更新之后，若 `on_streaming_update` 非 None 则调用 `on_streaming_update()`。

**Step 2: make_handlers 接受并传递 on_streaming_update**

在 `packages/basket-tui/basket_tui/native/handle/handlers.py` 中：
- `make_handlers` 增加参数 `on_streaming_update: Optional[Callable[[], None]] = None`。
- 在 `on_text_delta` 的 lambda 中调用 `handle_text_delta(..., on_streaming_update=on_streaming_update)`。

**Step 3: run.py 传入 on_streaming_update**

在 run.py 中构造 handlers 时传入 `on_streaming_update=lambda: (app_ref[0].invalidate() if app_ref else None)`（或等价 callable）。注意 make_handlers 在 app 创建之前被调用，故使用闭包 over app_ref 即可。

**Step 4: Run tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: PASS。若有 test_dispatch 或 test_handlers 需为 handle_text_delta 增加可选参数传 None 的用例，补上即可。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/handle/dispatch.py packages/basket-tui/basket_tui/native/handle/handlers.py packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(basket-tui): invalidate on text_delta for streaming display"
```

---

## Task 4: 集成测试（可选但推荐）

**Design ref:** §5 测试

**Files:**
- Modify or create: `packages/basket-tui/tests/native/test_run_integration.py` 或 `test_dispatch.py`

**Step 1: 添加集成断言**

例如：模拟 WebSocket 发送多条 text_delta，再发送 agent_complete；断言 body 内容在流式阶段包含 delta 文本，complete 后包含最终 Markdown 渲染的 assistant 块且无重复段落。可复用现有 test_run_integration 的 WebSocket 模拟方式，在 dispatch 或 run 的上下文中断言 get_body_lines() / body_lines 的阶段性内容。

**Step 2: Run**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-tui/tests/native/
git commit -m "test(basket-tui): integration test for streaming display"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-20-tui-streaming-display-plan.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** — Open a new session with executing-plans, batch execution with checkpoints.

Which approach?
