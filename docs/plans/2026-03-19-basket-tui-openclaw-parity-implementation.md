# Basket Native TUI OpenClaw 对标 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `basket tui` 的 native TUI 上实现设计文档《2026-03-19-basket-tui-openclaw-parity-design.md》中的视觉分层（A）与底栏计时/spinner、双击 Ctrl+C（B），Doctor 面板仅为客户端启发式。

**Architecture:** 在 `packages/basket-tui/basket_tui/native` 内扩展 `ui_state` / 布局与按键逻辑；复用现有 `make_handlers` 更新 phase；新增小型纯函数模块负责 ANSI 横幅、底栏格式化、Doctor 检测与双击退出状态机；用 pytest 覆盖可测逻辑。

**Tech Stack:** Python 3.12+、`prompt_toolkit`、`websockets`、pytest、`asyncio`。

**设计依据:** `docs/plans/2026-03-19-basket-tui-openclaw-parity-design.md`

---

### Task 1: Footer 格式化与 spinner（纯函数 + 测试）

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/footer.py`（或 `packages/basket-tui/basket_tui/native/ui/chrome.py`）
- Create: `packages/basket-tui/tests/native/test_footer.py`

**Step 1:** 编写 `format_footer(*, connection, phase, elapsed_s, spinner_index, exit_pending) -> str`（或返回 `list[Tuple[str,str]]` 供 FormattedText 使用），行为对齐设计文档 §4.1、§3 状态条。

**Step 2:** 运行 `cd packages/basket-tui && poetry run pytest tests/native/test_footer.py -v`，先确认测试失败（红）。

**Step 3:** 实现函数至测试通过（绿）。

**Step 4:** 提交：`git add ... && git commit -m "test(native-tui): footer format and spinner"`

---

### Task 2: Doctor 启发式（本地）+ 测试

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/doctor.py`
- Create: `packages/basket-tui/tests/native/test_doctor.py`

**Step 1:** 实现 `collect_doctor_notices(*, ws_url: str, connection_error: str | None) -> list[str]`（签名可调整）：至少覆盖「连接超时/失败」的说明性文案；避免泄露敏感路径。

**Step 2:** 测试：给定 `connection_error` 非空时返回非空列表；无错误时返回空列表。

**Step 3:** pytest 通过；提交。

---

### Task 3: 横幅 ANSI 构建 + 测试

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/banner.py`
- Create: `packages/basket-tui/tests/native/test_banner.py`

**Step 1:** 实现 `build_banner_lines(version: str) -> list[str]`，返回带 24-bit ANSI 的多行字符串（Basket 品牌 + 版本 + 标语），配色参考设计 §5。

**Step 2:** 测试：断言包含 `Basket`、版本子串、标语子串；可对 ANSI 转义做宽松匹配（或剥离后再断言核心文本）。

**Step 3:** pytest；提交。

---

### Task 4: `layout.py` 集成分区

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/ui/layout.py`
- Modify: `packages/basket-tui/tests/native/test_render.py`（若存在布局快照/高度断言）

**Step 1:** 扩展 `build_layout` 参数：`banner_lines`、`doctor_lines`（可选）、`footer_formatter` 回调或扩展 `ui_state` 键。

**Step 2:** 使用 `HSplit` 增加：横幅区（固定高度）、Doctor 区（有内容时 `Window` 若干行，否则 `Window(height=0)` 或占位策略在设计中二选一：**无内容不占高度**）。

**Step 3:** 顶栏 chrome 改为多行或 `FormattedText` 分段（agent/session/model 占位）。

**Step 4:** 运行 `poetry run pytest packages/basket-tui/tests/native/ -v`，修复破坏的测试；提交。

---

### Task 5: `run.py` 集成横幅、Doctor、底栏计时、双击 Ctrl+C

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Modify: `packages/basket-tui/basket_tui/native/handle/handlers.py`（若需同步 `ui_state` 键名）

**Step 1:** 连接前/后：生成 `banner_lines`；连接失败路径调用 `collect_doctor_notices`；成功连接后 Doctor 可为空。

**Step 2:** 在 `ui_state` 增加：`phase_started_at: float | None`（monotonic），在 handlers 内 phase 变化时更新；用 `asyncio` 定时任务每 0.25–1s `app.invalidate()` 刷新底栏秒数（注意取消任务 on exit）。

**Step 3:** 替换 `@kb.add("c-c")` 逻辑：引入 `ExitConfirmState`，第一次仅设置 flag + invalidate，第二次 `_do_exit`；`Ctrl+D` 与设计一致（推荐同双击）。

**Step 4:** 手动冒烟：`poetry run` 连接本地 gateway，检查横幅、底栏、双击退出。

**Step 5:** 提交。

---

### Task 6: 状态机与按键的单元测试

**Files:**
- Create: `packages/basket-tui/tests/native/test_exit_confirm.py`
- Optional: 抽离 `ExitConfirmState` 到 `packages/basket-tui/basket_tui/native/ui/exit_confirm.py` 便于测试

**Step 1:** 测试：首次 `on_ctrl_c` → pending；再次 → exit requested；`reset()` 或超时清除（若实现超时）。

**Step 2:** pytest；提交。

---

### Task 7: 文档与清单

**Files:**
- Modify: `packages/basket-tui/README.md` 或 `packages/basket-assistant/README.md`（TUI 小节）：说明双击 Ctrl+C、底栏含义。

**Step 2:** 在 `docs/plans/2026-03-15-tui-native-openclaw-checklist.md` 勾选已完成项或添加指向本计划的链接。

**Step 3:** 最终 `cd packages/basket-tui && poetry run pytest tests/native/ -v` 全绿；提交。

---

## 验证命令（整包）

```bash
cd packages/basket-tui && poetry run pytest tests/native/ -v
cd packages/basket-tui && poetry run ruff check basket_tui/native
cd packages/basket-tui && poetry run mypy basket_tui/native  # 若项目已启用
```

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-03-19 | 初版计划（writing-plans） |
