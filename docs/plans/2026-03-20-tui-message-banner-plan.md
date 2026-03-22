# TUI 消息区与 Banner 展示优化 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消息区 Tool 绿底与 User 区分、Assistant 前后各 1 行空行、Banner 层次清晰（品牌/version/tagline + 分隔线）。

**Architecture:** 仅改 render.py 样式与空行逻辑、banner.py 行样式与可选 layout 分隔线；body_lines / build_layout 接口不变。详见 `docs/plans/2026-03-20-tui-message-banner-design.md`。

**Tech Stack:** prompt_toolkit, Rich (Console/Text/Padding), basket-tui native (render.py, banner.py, layout.py), pytest。

---

## Task 1: Tool 块绿色系底色

**Design ref:** §2.1 — render.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/pipeline/render.py`
- Test: `packages/basket-tui/tests/native/test_render.py`

**Step 1: Write the failing test**

在 `packages/basket-tui/tests/native/test_render.py` 中新增：

```python
def test_render_messages_tool_block_uses_green_style_not_grey19():
    """Tool block uses green-ish background so it's distinct from user (grey23)."""
    messages = [{"role": "tool", "content": "read_file\nok"}]
    lines = render_messages(messages, width=80)
    text = "\n".join(lines)
    # grey19 (xterm 236) should not appear in tool styling; green (e.g. 22/28/29) should
    assert "grey19" not in text or "22" in text or "28" in text or "29" in text
    assert "read_file" in text and "ok" in text
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v -k "tool_block_green"`
Expected: FAIL（当前 Tool 仍为 grey19，断言可能失败或需随实现改为「输出含绿色 ANSI」）

**Step 3: Change Tool styles to green**

在 `packages/basket-tui/basket_tui/native/pipeline/render.py` 中：
- 将 `_TOOL_BG` 改为 256 色深绿底，例如 `"on colour22"` 或 `"on #2d2d2d"` 改为 `"on colour22"`（Rich 256: colour22 为 dark green）。
- 将 `_TOOL_HEADER_STYLE` 改为在绿底上的黄/金，如 `"bold yellow on colour22"`。
- 将 `_TOOL_BODY_STYLE` 改为绿底上的浅色，如 `"dim white on colour22"`。
- 删除或替换所有对 grey19 的引用。

**Step 4: Run tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v`
Expected: 全部通过（若 test 断言与实现不符，微调测试：例如只断言「无 grey19」或「含 colour22」）。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/pipeline/render.py packages/basket-tui/tests/native/test_render.py
git commit -m "fix(tui): tool block green background to distinguish from user"
```

---

## Task 2: Assistant 消息前后各 1 行空行

**Design ref:** §2.2 — render.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/pipeline/render.py`
- Test: `packages/basket-tui/tests/native/test_render.py`

**Step 1: Write the failing test**

在 `packages/basket-tui/tests/native/test_render.py` 中新增：

```python
def test_render_messages_assistant_has_blank_lines_above_and_below():
    """Assistant content has one blank line before and after."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello."},
        {"role": "user", "content": "Bye"},
    ]
    lines = render_messages(messages, width=80)
    # Find the assistant line(s); there must be at least one blank before and after
    text = "\n".join(lines)
    idx_hi = text.find("Hi")
    idx_hello = text.find("Hello")
    idx_bye = text.find("Bye")
    assert idx_hi < idx_hello < idx_bye
    between_hi_hello = text[idx_hi:idx_hello]
    between_hello_bye = text[idx_hello:idx_bye]
    # Blank line = newline with no or only whitespace between
    assert "\n\n" in between_hi_hello, "blank before assistant"
    assert "\n\n" in between_hello_bye, "blank after assistant"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v -k "assistant_has_blank"`
Expected: FAIL（当前 assistant 前后无专门空行）

**Step 3: Add blank lines around assistant in render_messages**

在 `render_messages` 的 for 循环中，当 `role == "assistant"` 且 content 非空时：
- 在调用 `_print_assistant(console, content)` **之前** 执行 `console.print()` 一次（空行）。
- 在调用 `_print_assistant(console, content)` **之后** 执行 `console.print()` 一次（空行）。
- 保持后续「每条消息后两空行」逻辑不变（即 assistant 块后仍有两空行再进入下一消息）。

**Step 4: Run tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_render.py -v`
Expected: 全部通过。

**Step 5: Commit**

```bash
git add packages/basket-tui/basket_tui/native/pipeline/render.py packages/basket-tui/tests/native/test_render.py
git commit -m "fix(tui): add blank lines above and below assistant messages"
```

---

## Task 3: Banner 层次清晰（品牌 / version / tagline）

**Design ref:** §3 — banner.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/banner.py`
- Test: `packages/basket-tui/tests/native/test_banner.py`
- Optional: `packages/basket-tui/basket_tui/native/ui/layout.py`（仅当统一分隔线时）

**Step 1: Write the failing test**

在 `packages/basket-tui/tests/native/test_banner.py` 中新增：

```python
def test_build_banner_brand_line_has_emphasis():
    """Brand line (Basket) has bold or stronger emphasis."""
    lines = build_banner_lines("1.0.0")
    assert len(lines) >= 1
    # ANSI bold is 1 (e.g. \x1b[1m)
    assert "Basket" in lines[0]
    assert "\x1b[1m" in lines[0] or "1;" in lines[0]

def test_build_banner_tagline_has_indent_or_border():
    """Tagline line has visual indent or leading border character."""
    lines = build_banner_lines("1.0.0")
    # Last non-empty content line is tagline
    tagline_line = [l for l in lines if "stop" in l or "ship" in l][0]
    stripped = re.sub(r"\x1b\[[0-9;]*m", "", tagline_line)
    assert stripped.startswith("  ") or stripped.startswith("│") or stripped.startswith("|")
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_banner.py -v -k "brand_line or tagline_indent"`
Expected: FAIL（当前可能无 bold、tagline 可能无缩进/边框）

**Step 3: Implement banner hierarchy in build_banner_lines**

在 `packages/basket-tui/basket_tui/native/ui/banner.py` 中：
- 品牌行：在现有橙色上增加 bold（ANSI `\x1b[1m` 或 Rich 等价），再 `_RESET`。
- Version 行：使用 dim（`\x1b[2m`）或更淡灰，保持「version x.y.z」文案。
- Tagline 行：在行首增加缩进（如 `  `）或细左边框（如 `  │ ` 或 `  | `），再接现有浅橙 tagline。
- 保持返回 4 行（或 3 行若去掉中间空行），签名不变。

**Step 4: Run tests**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_banner.py -v`
Expected: 全部通过。若有现有用例依赖精确 ANSI 字符串，需只断言结构/关键词。

**Step 5: (Optional) Separator line in layout**

若设计约定 Banner 下分隔线用双线或淡色：在 `layout.py` 中把 `sep_char` 改为 `═` 或给 `sep_control` 的 text 加上 dim 样式（需 FormattedTextControl 支持 ANSI）。否则可跳过。

**Step 6: Commit**

```bash
git add packages/basket-tui/basket_tui/native/ui/banner.py packages/basket-tui/tests/native/test_banner.py
git commit -m "fix(tui): banner hierarchy — bold brand, dim version, indented tagline"
```

---

## Task 4: Regression and manual check

**Step 1: Run full test suite**

Run: `cd packages/basket-tui && poetry run pytest -v`
Expected: 全部通过。

**Step 2: Manual check**

Run: `cd packages/basket-assistant && poetry run basket tui`（或从 repo root 对应命令），确认：
- User 块灰底、Tool 块绿底、Assistant 上下有空行、Banner 品牌醒目/version 淡/tagline 有缩进或边框。

**Step 3: Commit (if any fix)**

若有小修复则提交，否则跳过。

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-03-20-tui-message-banner-plan.md`.

**两种执行方式：**

1. **本会话子 agent 驱动** — 按 Task 1→2→3→4 依次派发子 agent，每步完成后你做 review，再进入下一步。
2. **独立会话批量执行** — 在新会话（建议 worktree）中打开本项目，使用 executing-plans 技能按任务顺序执行，在检查点做验证。

选哪种？
