# TUI 对话状态深度分析与改进建议

**日期**: 2025-03-08  
**范围**: basket-tui 与 basket-assistant TUI 模式下的对话状态（工具执行、等待模型、Thinking、流式输出等）  
**参考**: Claude Code 三阶段（Gather context / Take action / Verify）、Cursor IDE 状态反馈

---

## 一、当前实现概览

### 1.1 状态数据（AppState）

| 状态字段 | 含义 | 驱动来源 |
|----------|------|----------|
| `streaming_assistant` + `streaming_buffer` | 当前助手回复的流式缓冲 | `append_text()` / `ensure_assistant_block()` |
| `current_tool_name` / `current_tool_args` | 当前正在执行的工具 | `show_tool_call()` → `show_tool_result()` 清空 |
| `current_thinking_widget` / `thinking_block_index` | Thinking 块 | `append_thinking()` |
| `agent_task` | 当前 agent 异步任务 | `set_agent_task()`（run 开始/结束、cancel） |
| `output_blocks` / `output_blocks_with_role` | 已提交的对话块 | 各类 append/finalize |

**状态栏** 仅依赖 `agent_task` 与 `_pending_user_inputs`：

- `is_agent_running()` → 显示 `"Running... (N queued)"` 或 `"Running..."`
- 否则 → `"Ready"`

即：**没有区分「等待模型首 token」「思考中」「流式输出」「工具执行中」等子阶段**。

### 1.2 事件流（basket-assistant → basket-tui）

- **用户发送** → `ensure_assistant_block()` + `set_agent_task(task)` → 状态栏变为 "Running..."
- **首 token 前**：无专门事件，UI 上无法表达「正在连接/等待模型」
- **thinking_delta** → `append_message("system", "Thinking...")` + `append_thinking(delta)`（存在重复块风险，见下）
- **text_delta** → `append_text(delta)` → 流式区 + 缓冲
- **agent_tool_call_start** → `finalize_assistant_block()` + `show_tool_call(name, args)` → 输出块中显示「▶ tool(args)\n  执行中...」
- **agent_tool_call_end** → `show_tool_result(result, success)` → 同一块更新为结果
- **agent_complete** → `finalize_assistant_block()` + `post_message(ProcessPendingInputs)` + `set_agent_task(None)` → "Ready"
- **agent_error** → 追加 system 错误消息，任务结束也会清掉 `agent_task`

工具状态在**内容区**用「执行中...」/ 结果文案表达，**状态栏不区分**「等模型」与「跑工具」。

### 1.3 与「Codex 类」产品对比（Claude Code / Cursor）

- **Claude Code**：明确有 **Gather context / Take action / Verify** 等阶段，Planning 模式有「Planning」状态；工具块有 **Running / Interrupted / 结果** 的清晰状态线。
- **Cursor**：有「Taking longer than expected…」等等待态、Agent 有「Planning next moves」等阶段指示（尽管有 hang 的反馈，说明状态可见性对用户很重要）。
- **共同点**：  
  - 有**阶段/子状态**（等待、规划、执行工具、生成文本）；  
  - 工具块有**运行中 vs 完成/失败**的视觉区分；  
  - 长时间无反馈时有**超时/进度**提示。

当前 TUI：**阶段未显式建模**，状态栏只有「Running / Ready」，工具仅靠内容区「执行中...」和最终结果区分，缺少「等待模型」「思考中」的独立反馈。

---

## 二、已发现的具体问题

1. **Thinking 双块**：首次 `thinking_delta` 时既 `append_message("system", "Thinking...")` 又 `append_thinking(delta)`，后者在 `thinking_block_index is None` 时会再 append 一块，导致可能出现两个「Thinking」相关块。
2. **无「等待模型」状态**：从用户回车到第一个 text/thinking/tool 事件之间可能较长，状态栏只有 "Running..."，用户不知道是「等模型」还是「网络/卡住」。
3. **状态栏信息量不足**：不区分「流式输出中」「工具执行中」「思考中」，无法快速判断当前卡在模型还是工具。
4. **工具执行中无进度/耗时**：长时间工具（如 bash）只有「执行中...」，没有耗时或「第 N 个工具」等上下文。
5. **finalize 与 tool 的时序**：`show_tool_call` 会 `finalize_assistant_block()`，若之前只有 thinking 无 text，会保留 thinking 块；逻辑正确但和「阶段」未统一建模，后续扩展容易踩坑。
6. **错误/取消后状态**：取消或错误后 `set_agent_task(None)` 会变 "Ready"，但若存在未 `show_tool_result` 的 tool（例如取消时工具未返回），`current_tool_name` 可能仍非空，需与「当前块」展示一致。
7. **队列提示**：「N queued」只在状态栏，输入区无轻量提示，多条排队时不够明显。
8. **无超时/长时间运行提示**：没有「Running 超过 N 秒」的二次提示（如「Still running…」），与 Cursor 用户对「Taking longer than expected」的诉求类似。

---

## 三、改进建议（至少 10 条）

### 1. 显式建模「对话阶段」并在状态栏展示

- 在 TUI 侧引入**阶段枚举**（例如：`idle` | `waiting_model` | `thinking` | `streaming` | `tool_running` | `error`），由 agent 事件驱动：
  - 任务开始 → `waiting_model`
  - 首个 thinking_delta / text_delta / agent_tool_call_start → 切到对应阶段
  - agent_complete / agent_error → `idle`
- 状态栏根据阶段显示不同文案，例如：
  - `waiting_model` → 「等待模型…」
  - `thinking` → 「思考中…」
  - `streaming` → 「回复中…」或「Running...」
  - `tool_running` → 「工具执行中: tool_name」或「Running: tool_name」
  - 保留「(N queued)」在非 idle 时显示。

**产品价值**：用户一眼能区分「卡在模型」还是「卡在工具」，减少误判和重复操作。

---

### 2. 修复 Thinking 双块并统一为单一 Thinking 块

- 首次 thinking 时**不要**再 `append_message("system", "Thinking...")`，只调用 `append_thinking(delta)`，由后者唯一负责创建/更新「Thinking...」块。
- 若希望保留「系统级」提示，可仅在**尚无任何 thinking 块**时在状态栏显示「思考中…」（见建议 1），而不在 output_blocks 中插入额外 system 块。

**产品价值**：对话流更干净，复制/转录时不会出现重复的 Thinking 行。

---

### 3. 增加「run_start」或「waiting_model」事件

- 在 basket-assistant / agent 层，在真正发起首轮请求（或收到「开始流式」）时 emit 一个事件，例如 `run_start` 或 `waiting_model`。
- TUI 监听该事件，将阶段设为 `waiting_model` 并刷新状态栏；收到首个 content 类事件时切出该状态。

**产品价值**：从发送到首 token 的等待有明确反馈，与 Cursor/Claude 的「等待中」体验对齐。

---

### 4. 工具执行中显示工具名 + 可选耗时

- 状态栏在 `tool_running` 时显示当前 `current_tool_name`（如「工具: bash」）。
- 可选：在工具块或状态栏显示**已运行时间**（从 `show_tool_call` 到 `show_tool_result` 的计时），例如「执行中... 5s」。

**产品价值**：长命令时用户知道是哪个工具在跑、跑了多久，便于决定是否停止。

---

### 5. 工具块状态与阶段一致

- 工具块继续使用「执行中...」/「Running…」/ 结果 / 错误文案；同时保证 `AppState` 的 `current_tool_name` 与最后一块 tool 的展示一致。
- 在 `agent_error` 或 `cancel_agent_task` 时，若存在未结束的 tool，要么补一次 `show_tool_result(..., success=False)`，要么在状态机里标记「工具已中断」，避免「执行中」一直挂着。

**产品价值**：中断/错误后界面不留下「幽灵」执行中块。

---

### 6. 长时间运行与超时提示

- 当阶段为 `waiting_model` 或 `tool_running` 且持续时间超过阈值（如 15s / 30s）时，在状态栏或 notify 中增加二次提示：「Still waiting…」/「工具仍在执行，可 Ctrl+G 停止」。
- 可选：可配置阈值或仅在做 E2E/调试时启用。

**产品价值**：与 Cursor 用户对「Taking longer than expected」的诉求一致，减少「是不是卡死了」的焦虑。

---

### 7. 队列状态更可见

- 除状态栏「(N queued)」外，在输入区占位或下方做轻量提示（如「已排队 2 条，将在当前回复结束后发送」），或在 Footer 中固定显示排队数。
- 避免只在状态栏一闪而过，用户滚动时也能看到排队情况。

**产品价值**：多轮连续输入时，用户清楚知道哪些还没被处理。

---

### 8. 统一「阶段 → 状态栏 / 内容区」的单一数据源

- 以「阶段」为单一来源，驱动：状态栏文案、是否显示 live 区、是否显示 thinking 块、当前工具名等。
- `AppState` 可增加 `phase: Literal["idle", "waiting_model", ...]`，由事件层写入；状态栏和内容区只读 phase + 现有字段，避免多处 if/else 分散判断。

**产品价值**：后续加新阶段（如「规划中」「验证中」）时扩展简单、行为一致。

---

### 9. 错误与取消的明确反馈

- `agent_error` 时在状态栏短时显示「Error」或「已出错」，再在下一轮或 2s 后恢复为「Ready」。
- 用户 Ctrl+G 取消时，除现有「Stopped by user.」消息外，状态栏可短时显示「已停止」再变回「Ready」。
- 若有未结束的工具块，按建议 5 将其标记为中断/失败，避免仍显示「执行中」。

**产品价值**：操作有即时、一致的反馈，符合「Codex 类」产品的可预期性。

---

### 10. 转录/历史中保留阶段信息（可选）

- 在 `output_blocks_with_role` 或 transcript 导出中，可为「工具块」保留元数据：工具名、成功/失败、耗时（若实现建议 4）。不改变主界面，只让导出/调试信息更完整。

**产品价值**：回放、调试、分析对话时能还原「当时在等模型还是跑工具」。

---

### 11. 状态栏可点击或快捷键说明

- 状态栏显示「Running: bash」时，可支持点击或快捷键（如 Ctrl+E）跳转到「最后一个工具块」或展开工具结果；若已有「Expand last tool」，可在帮助中说明「当前在工具执行时也可用 Ctrl+E 查看结果」。

**产品价值**：降低「不知道现在在干什么」时的探索成本。

---

### 12. 与 Claude Code 的「Planning」对齐（可选）

- 若后续支持「仅规划不执行」模式（类似 Claude Code Planning 模式），可增加阶段 `planning`，状态栏显示「规划中…」，且工具块不执行或显示为「已跳过（规划模式）」。

**产品价值**：与用户对「规划 vs 执行」的心智模型一致。

---

## 四、实施优先级建议

| 优先级 | 建议 | 理由 |
|--------|------|------|
| P0 | 2（修复 Thinking 双块） | 明显 bug，易改 |
| P0 | 1（阶段 + 状态栏） | 状态可见性核心 |
| P1 | 3（waiting_model 事件） | 等待体验关键 |
| P1 | 4（工具名/耗时） | 工具可观测性 |
| P1 | 5（工具块与中断一致） | 避免幽灵「执行中」 |
| P2 | 6（长时间/超时提示） | 减少焦虑 |
| P2 | 7（队列可见性） | 多轮输入体验 |
| P2 | 8（阶段单一数据源） | 可维护性 |
| P2 | 9（错误/取消反馈） | 一致性 |
| P3 | 10–12 | 增强与扩展 |

---

## 五、小结

当前 TUI 的对话状态**以「是否有 agent_task」为主**，缺少对「等待模型 / 思考 / 流式 / 工具执行」的显式阶段划分和对应 UI 反馈。参考 Claude Code 与 Cursor 的做法，通过**显式阶段、状态栏细分、工具名/耗时、修复 Thinking 双块、超时与队列提示**等至少 12 条改进，可以在产品层面显著提升状态清晰度、可预期性和可观测性，并便于后续做规划模式、转录增强等扩展。
