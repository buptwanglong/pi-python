# basket-tui 按数据流分层 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 basket_tui/native 按 connection / handle / pipeline / ui 四层重组目录并清理冗余，不改变运行时行为。

**Architecture:** 见 docs/plans/2026-03-15-basket-tui-layout-design.md。connection 层放 WebSocket 与类型；handle 层放 make_handlers 与 dispatch；pipeline 层放 stream 与 render；ui 层放 layout、input_handler（合并 commands）、pickers。run.py 保留在 native 根仅做编排。

**Tech Stack:** Python 3.12+, pytest, 现有 basket-tui 依赖（prompt_toolkit, websockets, rich）。

---

### Task 1: 创建 connection 包并迁移

**Files:**
- Create: `packages/basket-tui/basket_tui/native/connection/__init__.py`
- Create: `packages/basket-tui/basket_tui/native/connection/client.py`（原 connection.py 内容）
- Create: `packages/basket-tui/basket_tui/native/connection/types.py`（原 types.py 内容）
- Modify: `packages/basket-tui/basket_tui/native/connection/client.py` 内 import：`from .types import GatewayHandlers`

**Step 1:** 创建 `basket_tui/native/connection/__init__.py`，导出 `GatewayWsConnection`、`GatewayHandlers`、`GatewayConnectionProtocol`（from .client 与 .types）。

**Step 2:** 复制 `basket_tui/native/connection.py` 内容到 `connection/client.py`，将 `from .types` 改为 `from .types`（同包），类与函数不变。

**Step 3:** 复制 `basket_tui/native/types.py` 内容到 `connection/types.py`，无导入修改。

**Step 4:** 运行现有与 connection 相关的测试并修正导入（本 Task 内先改 test_connection 的导入，其余测试在对应 Task 中更新）。此处可先运行：`cd packages/basket-tui && poetry run pytest tests/native/test_connection.py -v`，将测试内导入改为 `from basket_tui.native.connection import ...` 或 `from basket_tui.native.connection.client import ...` 使通过。

**Step 5:** Commit: `feat(basket-tui): add native.connection package (client + types)`

---

### Task 2: 创建 pipeline 包并迁移

**Files:**
- Create: `packages/basket-tui/basket_tui/native/pipeline/__init__.py`
- Create: `packages/basket-tui/basket_tui/native/pipeline/stream.py`（原 stream.py）
- Create: `packages/basket-tui/basket_tui/native/pipeline/render.py`（原 render.py）

**Step 1:** 复制 `native/stream.py` 到 `pipeline/stream.py`，复制 `native/render.py` 到 `pipeline/render.py`，无跨包导入需改。

**Step 2:** `pipeline/__init__.py` 导出 `StreamAssembler`、`render_messages`。

**Step 3:** 运行 `pytest tests/native/test_stream.py tests/native/test_render.py -v`，更新测试导入为 `from basket_tui.native.pipeline import ...`，使通过。

**Step 4:** Commit: `feat(basket-tui): add native.pipeline package (stream + render)`

---

### Task 3: 创建 handle 包并迁移

**Files:**
- Create: `packages/basket-tui/basket_tui/native/handle/__init__.py`
- Create: `packages/basket-tui/basket_tui/native/handle/handlers.py`（原 handlers.py）
- Create: `packages/basket-tui/basket_tui/native/handle/dispatch.py`（原 dispatch.py，并删除 _make_output_put）

**Step 1:** 创建 `handle/__init__.py`，导出 `make_handlers`（及测试用的 _dispatch_ws_message 可从 handle.dispatch 导入）。

**Step 2:** 复制 `native/handlers.py` 到 `handle/handlers.py`。修改导入：`from .dispatch import ...`，`from ..pipeline.stream import StreamAssembler`，`from ..pipeline.render import render_messages`；`GatewayHandlers` 从 `..connection.types` 导入。

**Step 3:** 复制 `native/dispatch.py` 到 `handle/dispatch.py`。删除 `_make_output_put` 函数及 `queue`、`threading` 导入。修改导入：`from ..pipeline.render import render_messages`，`from ..pipeline.stream import StreamAssembler`。

**Step 4:** 运行 `pytest tests/native/test_dispatch.py tests/native/test_handlers.py -v`，更新测试导入为 `from basket_tui.native.handle...`，使通过。

**Step 5:** Commit: `feat(basket-tui): add native.handle package, remove _make_output_put from dispatch`

---

### Task 4: 创建 ui 包并合并 commands

**Files:**
- Create: `packages/basket-tui/basket_tui/native/ui/__init__.py`
- Create: `packages/basket-tui/basket_tui/native/ui/layout.py`（原 layout.py）
- Create: `packages/basket-tui/basket_tui/native/ui/pickers.py`（原 pickers.py）
- Create: `packages/basket-tui/basket_tui/native/ui/input_handler.py`（原 input_handler + commands 内容）

**Step 1:** 复制 `native/layout.py` 到 `ui/layout.py`，复制 `native/pickers.py` 到 `ui/pickers.py`。pickers 内无对 types 的引用；若有可从 `..connection.types` 导入协议（本包内 input_handler 需要）。

**Step 2:** 将 `native/commands.py` 中 HELP_LINES、SlashResult、handle_slash_command 移入 `ui/input_handler.py`。将原 `native/input_handler.py` 内容并入：删除 `from .commands import ...`，改为本模块内定义的 HELP_LINES 与 handle_slash_command。GatewayConnectionProtocol 从 `basket_tui.native.connection` 或 `..connection` 导入。pickers 从 `.pickers` 导入。

**Step 3:** `ui/__init__.py` 导出 `build_layout`、`handle_input`、`open_picker`、`HELP_LINES`（若对外需要）、`InputResult`。

**Step 4:** 运行 `pytest tests/native/test_input_handler.py tests/native/test_pickers.py -v`，更新测试导入为 `from basket_tui.native.ui import ...`；若有 test_commands 或对 commands 的测试，改为对 input_handler 的测试并更新导入。使通过。

**Step 5:** Commit: `feat(basket-tui): add native.ui package, merge commands into input_handler`

---

### Task 5: 更新 run.py 与 native/__init__.py

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Modify: `packages/basket-tui/basket_tui/native/__init__.py`

**Step 1:** 在 run.py 中：`from .connection import GatewayWsConnection`（或 from .connection.client），`from .handle import make_handlers`，`from .pipeline import StreamAssembler`，`from .ui.input_handler import handle_input, open_picker`，`from .ui.layout import build_layout`。删除对 connection.py、handlers.py、stream、input_handler、layout 的旧导入。

**Step 2:** 运行 `pytest tests/native/test_run.py tests/native/test_run_integration.py -v`。测试内对 _dispatch_ws_message 的导入改为 `from basket_tui.native.handle.dispatch import _dispatch_ws_message`；对 assembler、output_put 等仍从 pipeline/handle 取。修正至全部通过。

**Step 3:** 更新 `native/__init__.py`：从 .run 导出 run_tui_native_attach；从 .connection 导出 GatewayWsConnection、GatewayHandlers、GatewayConnectionProtocol；从 .handle 导出 make_handlers；从 .pipeline 导出 StreamAssembler、render_messages。保持与当前 __all__ 兼容。

**Step 4:** 运行全包测试：`cd packages/basket-tui && poetry run pytest -v`。通过则提交。

**Step 5:** Commit: `feat(basket-tui): wire run and native __init__ to connection/handle/pipeline/ui`

---

### Task 6: 删除旧文件并收尾

**Files:**
- Delete: `packages/basket-tui/basket_tui/native/connection.py`
- Delete: `packages/basket-tui/basket_tui/native/types.py`
- Delete: `packages/basket-tui/basket_tui/native/handlers.py`
- Delete: `packages/basket-tui/basket_tui/native/dispatch.py`
- Delete: `packages/basket-tui/basket_tui/native/stream.py`
- Delete: `packages/basket-tui/basket_tui/native/render.py`
- Delete: `packages/basket-tui/basket_tui/native/commands.py`
- Delete: `packages/basket-tui/basket_tui/native/input_handler.py`
- Delete: `packages/basket-tui/basket_tui/native/layout.py`
- Delete: `packages/basket-tui/basket_tui/native/pickers.py`

**Step 1:** 确认所有测试与 `poetry run basket tui`（或 examples/tui_example）均使用新包路径且通过。

**Step 2:** 按上表删除 native 根下已迁移的 10 个文件。

**Step 3:** 再次运行 `poetry run pytest -v` 与手动跑一次 TUI，确认无回归。

**Step 4:** Commit: `chore(basket-tui): remove old flat native modules after layout refactor`

---

### Task 7:（可选）测试 helper 与 _dispatch_ws_message

**Files:**
- Optional: Create `packages/basket-tui/tests/native/helpers.py`，将 _dispatch_ws_message 复制为 dispatch_ws_message_for_test（或保留在 handle.dispatch 中由测试导入）。

若保留 _dispatch_ws_message 在 handle/dispatch.py，则无需本 Task。若希望测试与实现解耦，可在 helpers.py 中 re-export：`from basket_tui.native.handle.dispatch import _dispatch_ws_message as dispatch_ws_message_for_test`，测试改为从 helpers 导入。执行后运行测试并提交。

---

## 执行选项

计划已保存到 `docs/plans/2026-03-15-basket-tui-layout-plan.md`。

**两种执行方式：**

1. **Subagent-Driven（本会话）** — 按任务派发子 agent，每步完成后审查，再进入下一步。
2. **Parallel Session（新会话）** — 在新会话中用 executing-plans 在独立 worktree 中按检查点批量执行。

选哪一种？
