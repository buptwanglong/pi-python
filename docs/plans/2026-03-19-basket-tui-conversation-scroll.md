# Basket TUI 对话区滚动与粘性底部 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 native TUI 对话区支持纵向滚动、默认自动滚到底，并在用户上滚后暂停自动跟底直至 Ctrl+End 恢复。

**Architecture:** 在 `prompt_toolkit` 对话 `Window` 上使用 `get_vertical_scroll` 与 `FormattedTextControl.get_cursor_position` 驱动垂直滚动；`run.py` 维护 `follow_tail` 与 `body_scroll`；统一经 `output_put` 追加 transcript；开启 `mouse_support` 以支持滚轮。

**Tech Stack:** Python 3.12+、`prompt_toolkit`、现有 `basket_tui.native` 布局与 WebSocket 输出链。

**设计依据:** `docs/plans/2026-03-19-basket-tui-conversation-scroll-design.md`

---

### Task 1: 滚动纯函数 + 单元测试

**Files:**

- Create: `packages/basket-tui/basket_tui/native/ui/scroll_state.py`（或 `native/scroll_math.py`，与包内命名一致即可）
- Create: `packages/basket-tui/tests/native/test_scroll_state.py`

**Step 1: 写失败测试**

定义并实现（先测后实现或 TDD）：

- `clamp_scroll(scroll: int, content_height: int, window_height: int) -> int`
- `max_scroll(content_height: int, window_height: int) -> int`
- （可选）`scroll_page_up` / `scroll_page_down` 接受 `page_size: int`

覆盖：`content_height <= window_height`；`scroll` 负值与超大值；resize 后 `window_height` 变大/变小。

**Step 2: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_scroll_state.py -v`  
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/scroll_state.py packages/basket-tui/tests/native/test_scroll_state.py
git commit -m "test(tui): add scroll clamp helpers for conversation viewport"
```

---

### Task 2: 统一 transcript 追加入口

**Files:**

- Modify: `packages/basket-tui/basket_tui/native/ui/input_handler.py`
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Test: `packages/basket-tui/tests/native/test_input_handler.py`（更新 mock / 签名）

**Step 1: 改 `handle_input` / `_run_picker` 签名**

将 `body_lines: list[str]` 改为 `output_put: Callable[[str], None]`（或 `Protocol`），所有原 `body_lines.append` / `extend` 改为对每行调用 `output_put(line)`（`HELP_LINES` 用循环）。

**Step 2: `run.py`**

- `handle_input(text, base_url, conn, output_put)`  
- 连接成功后 `[system] Connected` 改为 `output_put(...)`（若尚未走同一函数则合并）。

**Step 3: 运行相关测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_input_handler.py -v`  
Expected: PASS（按需更新测试里的调用方式）

**Step 4: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/input_handler.py packages/basket-tui/basket_tui/native/run.py packages/basket-tui/tests/native/test_input_handler.py
git commit -m "refactor(tui): route transcript appends through output_put"
```

---

### Task 3: `build_layout` 接入滚动回调

**Files:**

- Modify: `packages/basket-tui/basket_tui/native/ui/layout.py`
- Modify: `packages/basket-tui/basket_tui/native/ui/__init__.py`（若需导出）
- Test: `packages/basket-tui/tests/native/test_layout.py`（若无则新建轻量测试：调用 `build_layout` 不抛错，可用 mock 回调）

**Step 1: 扩展 `build_layout` 参数**

为对话 `Window` 传入：

- `get_vertical_scroll: Callable[[Any], int]`（接收 `Window`）
- `get_cursor_position: Callable[[], Point]`（或 PTK 要求的可调用）
- `always_hide_cursor=True`

保持 `body_lines` 与 `FormattedTextControl` 的 `ANSI` 拼接方式不变。

**Step 2: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest packages/basket-tui/tests/native/ -v --ignore=...` 或全量 `tests/native/`  
Expected: PASS

**Step 3: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/layout.py packages/basket-tui/basket_tui/native/ui/__init__.py packages/basket-tui/tests/native/test_layout.py
git commit -m "feat(tui): wire conversation Window to vertical scroll hooks"
```

---

### Task 4: `run.py` 状态机、键绑定、鼠标

**Files:**

- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 状态容器**

例如 `follow_tail: list[bool] = [True]`、`body_scroll: list[int] = [0]`（或与现有 `app_ref` 风格一致的可变单元素盒）。

**Step 2: 实现 `get_vertical_scroll` / `get_cursor_position`**

- 在 `get_vertical_scroll(window)` 内：读取 `window.render_info`（若可用）得到 `content_height`、`window_height`；`follow_tail` 为真时返回 `max_scroll`；否则返回 `clamp_scroll(body_scroll, ...)`。  
- **Spike 验证**：与 `wrap_lines` 下 `line_count` 一致；若首帧无 `render_info`，返回 `0` 或安全默认值。  
- `get_cursor_position`：返回与当前滚动一致的 `Point`，避免 `do_scroll` 把视口拉回顶行（按设计文档 §2）。

**Step 3: 键绑定**

- `pageup` / `pagedown`：更新 `follow_tail` / `body_scroll`，`invalidate`。  
- `c-end`：`follow_tail=True`，`invalidate`。

**Step 4: `Application`**

- `mouse_support=True`。  
- 若滚轮与 `get_vertical_scroll` 不同步：在 `Window` 的 mouse handler 或全局绑定中同步 `body_scroll`（以 spike 结果为准）。

**Step 5: `output_put`**

- 保持 append + invalidate；若需在新行到达且 `follow_tail` 时强制贴底，仅在回调内设置状态，避免重复逻辑。

**Step 6: 运行测试**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`  
Expected: PASS

**Step 7: Commit**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(tui): sticky-bottom scrolling for conversation area"
```

---

### Task 5: 文档与 HELP

**Files:**

- Modify: `packages/basket-tui/basket_tui/native/ui/input_handler.py`（`HELP_LINES`）
- Modify: `packages/basket-tui/README.md`（若存在快捷键表）

**Step 1:** 在 `/help` 中增加一行：滚动 / Page Up·Down / Ctrl+End 跟随最新。

**Step 2: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/input_handler.py packages/basket-tui/README.md
git commit -m "docs(tui): document conversation scroll shortcuts"
```

---

### Task 6: 手工验收清单（必做）

1. 启动 native TUI 并产生多屏输出。  
2. 滚轮与 Page Up/Down 可浏览历史。  
3. 默认新消息自动在底部。  
4. 上滚后新消息不抢视口；Ctrl+End 恢复跟底。  
5. 缩小/放大终端窗口无异常。

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-03-19-basket-tui-conversation-scroll.md`. Two execution options:

1. **Subagent-Driven (this session)** — 每任务派生子代理，任务间 review，迭代快  
2. **Parallel Session (separate)** — 新会话用 executing-plans，分批执行与检查点  

Which approach?
