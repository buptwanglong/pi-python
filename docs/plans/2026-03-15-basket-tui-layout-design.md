# basket-tui 按数据流分层 — 设计

**日期**: 2026-03-15  
**目标**: 将 `native/` 平铺文件按「connection → handle → pipeline → ui」分层，并清理冗余。

---

## 1. 目录与模块归属

```
basket_tui/
  __init__.py                    # 不变：from .native.run import run_tui_native_attach
  native/
    __init__.py                  # 重导：run + 各层对外类型/工厂
    run.py                       # 保留在根：只做编排，从各子包导入
    connection/
      __init__.py
      client.py                  # 原 connection.py（GatewayWsConnection）
      types.py                   # 原 types.py
    handle/
      __init__.py
      handlers.py                # 原 handlers.py
      dispatch.py                # 原 dispatch.py（删 _make_output_put）
    pipeline/
      __init__.py
      stream.py                  # 原 stream.py
      render.py                  # 原 render.py
    ui/
      __init__.py
      layout.py                  # 原 layout.py
      input_handler.py           # 原 input_handler + 合并 commands
      pickers.py                 # 原 pickers.py
```

- **connection**：WebSocket 连接、收发、按 type 调 GatewayHandlers；不依赖 pipeline/ui。
- **handle**：make_handlers 依赖 pipeline（StreamAssembler、render_messages）与 output_put；dispatch 的 handle_* 仅依赖 stream + render + output_put。
- **pipeline**：stream 与 render 无 handle/connection 依赖。
- **ui**：layout / input_handler / pickers 仅依赖 connection 的协议（GatewayConnectionProtocol）。

删除 **commands.py**：斜杠解析与 HELP_LINES 并入 **ui/input_handler.py**。  
**dispatch.py** 删除 **\_make_output_put**；**\_dispatch_ws_message** 保留供测试用，或迁至 `tests/native/helpers.py`。

---

## 2. 数据流与清理

**上行（用户 → Gateway）**  
`run` → ui.input_handler.handle_input / open_picker → connection.send_message | send_abort | send_switch_session 等。

**下行（Gateway → 界面）**  
connection 收消息 → handle.GatewayHandlers（make_handlers 构造）→ handle.dispatch.handle_* → pipeline.stream（StreamAssembler）+ pipeline.render（render_messages）+ output_put（body_lines.append + app.invalidate）。

**合并 commands 进 input_handler**  
- 将 HELP_LINES、SlashResult、handle_slash_command 移入 ui/input_handler.py。  
- input_handler 内：先处理已实现的斜杠（/session、/agent、/new、/abort、/settings、/help），再对以 "/" 开头的调用原 handle_slash_command 逻辑（/exit → "exit"，未知 → "handled"）。  
- 保持 InputResult = "send" | "exit" | "handled" 不变。

**dispatch 清理**  
- 删除 _make_output_put（queue/threading 未使用）。  
- _dispatch_ws_message：保留在 handle/dispatch.py 供 tests 调用；或迁到 tests/native/helpers.py 并重命名为 e.g. dispatch_ws_message_for_test，由 test_run / test_run_integration 使用。

---

## 3. 对外 API 与测试

**basket_tui/__init__.py**  
不变：`from .native.run import run_tui_native_attach`。

**native/__init__.py**  
从各子包重导，保持现有对外名可用（可选）：  
- run_tui_native_attach（from .run）  
- GatewayWsConnection、GatewayConnectionProtocol、GatewayHandlers（from .connection）  
- make_handlers、render_messages、StreamAssembler（from .handle / .pipeline，按当前 __all__ 需要）

**测试**  
- 目录与包对应：tests/native/ 下可按 tests/native/connection/、tests/native/handle/、tests/native/pipeline/、tests/native/ui/ 分子目录，或保持 tests/native/*.py 但更新 import 路径。  
- 所有 from basket_tui.native.xxx 改为 from basket_tui.native.connection.client、basket_tui.native.handle.dispatch 等。  
- 依赖 _dispatch_ws_message 的测试：继续 from basket_tui.native.handle.dispatch import _dispatch_ws_message，或改为从 tests/native/helpers 导入（若迁移）。

---

## 4. 不做的

- 不改变单 asyncio 循环、无 queue.Queue/threading 的运行时行为。  
- 不新增功能、不改 Gateway 协议。  
- pipeline 内不合并 stream 与 render 为单文件（保持两文件）。
