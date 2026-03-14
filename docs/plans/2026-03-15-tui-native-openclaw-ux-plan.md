# tui-native OpenClaw 式展示与交互优化 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 tui-native 基础上补齐 P0（工具块渲染、固定 Header/Footer）与 P1（Esc 中止、Ctrl+P/G/L picker、/settings、/model 语义），使展示与交互对齐 OpenClaw 式 TUI。

**Architecture:** 保持 line-output + prompt_toolkit 架构；在 run.py 中增加「上次已渲染消息下标」、Header/Footer 状态与刷新逻辑；dispatch 时在 tool_call_end 与 agent_complete 输出新增消息；布局中固定首行为 Header、末行为 Footer；快捷键与 /settings 在 run.py/commands 中扩展。

**Tech Stack:** Python 3.12+, prompt_toolkit, Rich, 现有 basket_tui.native（render, stream, pickers, commands）。

**设计依据:** `docs/plans/2026-03-15-tui-native-openclaw-checklist.md`

---

## Phase P0：必须项

### Task 1: 工具块参与渲染并在聊天区输出

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Test: `packages/basket-tui/tests/native/test_run.py` 或 `test_run_integration.py`

**Step 1: 明确当前行为并写断言**

在 `_dispatch_ws_message` 中，当前仅在 `agent_complete` 时渲染并 output 最后一条消息（assistant）。工具块已进入 `assembler.messages` 但从未被渲染。  
在 `tests/native/test_run.py` 或新建测试中：mock 或集成地发送 `tool_call_start`、`tool_call_end`、`agent_complete`，断言最终输出（stdout 或 output_queue）中包含工具名或工具结果片段（可 strip ANSI 后 assert substring）。

**Step 2: 运行测试，确认失败**

Run: `cd packages/basket-tui && poetry run pytest tests/native/test_run.py -v -k tool`  
Expected: 无匹配测试则先加测试并看到「输出中无工具内容」的失败。

**Step 3: 实现「仅输出新增消息」**

- 在 `_async_main` 中为 assembler 维护「上次已输出消息数」`last_output_count`（或传入 `_dispatch_ws_message` 的 ref）。
- 在 `tool_call_end` 分支：不在这里直接 output，仅依赖 assembler 已 append tool message。
- 在 `agent_complete` 分支：不再只渲染 `[last]`，改为从 `assembler.messages[last_output_count:]` 渲染整段（即所有未输出的消息：可能包含多条 tool + 一条 assistant），对每一条 message 调用 `render_messages([m], width)` 得到 lines 并依次 `output_put(line)`；然后将 `last_output_count` 设为 `len(assembler.messages)`。
- 若希望在每次 tool 结束时立即看到工具块：可在 `tool_call_end` 分支里对刚 append 的那条 tool message 立即 render 并 output，并增加 `last_output_count`。二选一：要么只在 agent_complete 时一起输出（实现简单），要么 tool_call_end 也输出（体验更好）。建议先做「agent_complete 时输出所有未输出消息」。

**Step 4: 运行测试，确认通过**

Run: `cd packages/basket-tui && poetry run pytest tests/native/ -v`  
Expected: PASS（含新工具块断言）。

**Step 5: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py packages/basket-tui/tests/native/
git commit -m "feat(basket-tui): render tool blocks in native chat on agent_complete"
```

---

### Task 2: 固定 Header 行（URL + agent + session）并在切换后刷新

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 增加 Header 状态**

在 `run_tui_native_attach` 中（或传给 async 的共享状态）：增加 `current_agent: str`、`current_session: str`，初始值从启动参数或 "default" 取；WebSocket 侧在 `session_switched` / `agent_switched` 时更新这些值，并往 output_queue 放一条特殊标记（例如 `("header",)`）表示需刷新 header，或由主线程在 poll 时根据 session_switched/agent_switched 的 last 状态生成 header 文案。

**Step 2: 布局中首行显示 Header**

当前 layout 为 `HSplit([Window(body_control), Window(sep), VSplit([prompt, input])])`。在 body_control 之前插入一行：`FormattedTextControl(text=lambda: header_line)`，其中 `header_line` 来自共享状态，例如 `f"  URL={_http_base_url(ws_url)}  agent={current_agent}  session={current_session}"`。确保 `current_agent`/`current_session` 在主线程可读（例如 list ref 或 queue 传一次）。

**Step 3: 切换后更新状态并刷新**

- 在 `_dispatch_ws_message` 的 `session_switched` 分支：设置 `session_id` 到共享状态（需把 ref 传入 dispatch 或通过 output_put 传一条带 session 的标记，由 consumer 更新 ref）。
- 在 `agent_switched` 分支：同理更新 agent 状态。
- 主线程在 `_poll_output` 中若从 output_queue 取到 header 刷新标记，则更新 `current_agent`/`current_session` 并 invalidate，使首行重绘。  
实现方式可简化：不在 queue 里传 header 标记，而在每次 poll 后根据「最近一次 session_switched/agent_switched 的 payload」更新 ref，并让 header 的 lambda 读该 ref，这样只要有一次 output_put 后 invalidate，下一帧就会用新 ref 画 header。更简单：session_switched/agent_switched 时除了 output_put 系统提示外，再 put 一条如 `("\rheader", agent, session)`，主线程收到后更新 ref 并 invalidate。

**Step 4: 手动验证**

Run: `basket tn`，执行 `/session` 或 `/agent` 切换，确认首行 URL/agent/session 更新。

**Step 5: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(basket-tui): fixed header line with URL, agent, session; refresh on switch"
```

---

### Task 3: 固定 Footer/Status 行（连接状态 + phase）

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 增加 phase 与连接状态**

定义简单枚举或字符串：`phase in ("idle", "streaming", "tool_running", "error")`，`connection in ("connecting", "connected", "disconnected")`。在 `_async_main` 中维护这两个状态（可放在 list/dict ref 中供 dispatch 与主线程读）。

**Step 2: 在 dispatch 中更新 phase/connection**

- `text_delta` → phase = "streaming"
- `tool_call_start` → phase = "tool_running"
- `tool_call_end` 且无后续 streaming 时可保持或置回 "idle"（或在 agent_complete 时置 "idle"）
- `agent_complete` → phase = "idle"
- `agent_error` → phase = "error"
- WebSocket 连接成功 → connection = "connected"；断开/重连中 → "disconnected" / "connecting"

**Step 3: 布局中增加 Footer 行**

在 separator 与 input 之间（或 separator 之上）加一行：`FormattedTextControl(text=lambda: footer_line)`，`footer_line` 例如 `f"  {connection} | {phase}"`，宽度用 width 截断。主线程通过 ref 读取 phase/connection，poll 时若发现变化则 invalidate。

**Step 4: 将 phase/connection 从 async 传到主线程**

通过 output_queue 传状态更新：例如 put `("state", "phase", "streaming")` 或 `("state", "connection", "connected")`，主线程 poll 时处理这些元组并更新 ref，然后 invalidate。或复用现有 output_put，在每次状态变化时 put 一条特殊行由主线程解析；更干净的是单独一个小 queue 或在同一 queue 里用 tuple 区分。

**Step 5: 手动验证**

Run: `basket tn`，发一条消息，观察 footer 是否从 idle → streaming（或 tool_running）→ idle。

**Step 6: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(basket-tui): footer/status line with connection and phase"
```

---

## Phase P1：强烈建议

### Task 4: Esc 中止当前轮次

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 绑定 Esc**

在 prompt_toolkit KeyBindings 中 `@kb.add("escape")`：若当前有运行中状态（phase 非 idle），则向 thread_queue 放入 `("abort",)`（与 `/abort` 相同逻辑），并可选 output_put("[system] Aborted.")；若 phase 为 idle，则可为「清空输入」或 no-op。先做「Esc = 发送 abort」即可。

**Step 2: 手动验证**

Run: `basket tn`，发一条会触发工具调用的消息，在未完成前按 Esc，确认收到 Aborted 并停止。

**Step 3: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(basket-tui): Esc sends abort in native TUI"
```

---

### Task 5: Ctrl+P / Ctrl+G / Ctrl+L 打开 session / agent / model picker

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`

**Step 1: 绑定快捷键**

在 KeyBindings 中：
- `Ctrl+P`：执行与 `/session` 相同逻辑（run_session_picker，然后 thread_queue.put(("switch_session", session_id))）。
- `Ctrl+G`：执行与 `/agent` 相同逻辑（run_agent_picker，然后 put(("switch_agent", agent_name))）。
- `Ctrl+L`：执行与 `/model` 相同逻辑（run_model_picker，然后 put；见 Task 7 的 /model 语义）。

**Step 2: 确保 picker 在 full_screen 下可显示**

当前 run_session_picker 等为阻塞调用，在 main 线程执行；绑定后从 key 事件中调用同一逻辑即可。

**Step 3: 手动验证**

Run: `basket tn`，按 Ctrl+P / Ctrl+G / Ctrl+L，确认选择器弹出且选择后生效。

**Step 4: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "feat(basket-tui): Ctrl+P/G/L open session, agent, model picker"
```

---

### Task 6: /settings 实现（至少部分）

**Files:**
- Create or Modify: `packages/basket-tui/basket_tui/native/settings.py`（可选）
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- Modify: `packages/basket-tui/basket_tui/native/commands.py`

**Step 1: 定义可配置项**

与 gateway 或本地一致：例如「显示思考过程」「展开工具输出」等。若 gateway 无对应 API，可先做本地状态（如 `show_thinking: bool`），仅影响本地渲染，为后续对接预留。

**Step 2: /settings 打开 overlay 或简单菜单**

用 prompt_toolkit 显示一个简单列表：例如 "Toggle thinking (Ctrl+T)"、"Toggle tool expand (Ctrl+O)"，选择后切换状态并关闭。若不做 overlay，可先实现为「打印当前设置 + 说明后续可扩展」。

**Step 3: 提交**

```bash
git add packages/basket-tui/basket_tui/native/
git commit -m "feat(basket-tui): /settings overlay or stub with placeholders"
```

---

### Task 7: /model 语义修正与 gateway 对齐

**Files:**
- Modify: `packages/basket-tui/basket_tui/native/run.py`
- 可选: `packages/basket-gateway`（若需新增 switch_model）

**Step 1: 确认 gateway API**

当前 gateway 仅有 `switch_agent`，无 `switch_model`。若产品上「模型」与「agent」一一对应，则 /model 与 model picker 可视为「选 agent（其背后是某模型）」并保持调用 `switch_agent`，但在 UI 文案和 /help 中写清「model 选择即切换使用该模型的 agent」。若后续 gateway 增加 `switch_model`，再在 run.py 中增加分支发送 `switch_model`。

**Step 2: 修正误用**

当前 `/model` 选择后调用了 `switch_agent`（与 /agent 重复）。二选一：  
- A) 保留 model picker，但改为「列出模型名 → 选后切换至使用该模型的 agent」（需 gateway 或配置提供 model→agent 映射）；  
- B) 暂时将 /model 与 Ctrl+L 改为「显示当前模型信息」或跳转到 /agent，并在 /help 中说明「模型随 agent 而定」。  
采用 B 更简单：/model 与 Ctrl+L 打开「当前 agent 对应的模型」只读展示或直接打开 agent picker，并修正 run.py 中 model picker 回调不要误写为 switch_agent（若选的是 model 而非 agent，则只展示不切换，或文档说明当前用 agent 代表模型）。

**Step 3: 提交**

```bash
git add packages/basket-tui/basket_tui/native/run.py
git commit -m "fix(basket-tui): /model and model picker semantics; align with gateway"
```

---

## 完成与验收

- 跑全量测试：`cd packages/basket-tui && poetry run pytest -v`
- 手动：`basket tn` 下验证 Header/Footer、工具块展示、Esc、Ctrl+P/G/L、/settings、/model 行为。
- 计划完成后可在同一文档或 checklist 中标注「P0/P1 已完成」，再按需排 P2。

---

## 执行选项

**Plan complete and saved to `docs/plans/2026-03-15-tui-native-openclaw-ux-plan.md`.**

**两种执行方式：**

1. **本会话子 agent 驱动** — 按任务逐个派发子 agent，每任务后你做 review，迭代快。  
2. **并行会话** — 在新会话（或 worktree）中用 executing-plans 按检查点批量执行。

你选哪种？
