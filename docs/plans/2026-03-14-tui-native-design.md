# 终端原生 TUI 设计（tui-native）

## 目标与范围

- **目标**：在保留现有 Textual TUI（`basket tui`）的前提下，新增子命令 `basket tui-native`（别名 `basket tn`），采用「按行输出到终端」的模型，实现 Markdown 渲染 + 终端选区复制，并在能力上尽量对齐现有 TUI（picker、设置、快捷键等）。
- **范围**：同包（basket-tui）内新模块 + prompt_toolkit；不拆新包，不复用 Textual。Gateway 连接、消息协议与现有 attach 模式一致。

---

## 1. 架构

- **入口**：basket-assistant 的 `main.py` 在解析到子命令 `tui-native`（或 `tn`) 时，与现有 `tui` 一样先确保 gateway 已启动、解析 `--agent` 等，然后调用 `run_tui_native_attach(ws_url, agent_name=..., max_cols=...)`。该函数可放在 `basket_assistant.modes` 或由 basket-tui 提供；推荐由 **basket-tui** 提供 `run_tui_native_attach`，basket-assistant 仅负责解析与调用，以保持「TUI 实现」在 basket-tui 内。
- **输出模型**：所有「内容」（header、历史消息、工具块、流式缓冲区、footer）均通过 **sys.stdout 写入 ANSI 字符串**，按行输出，不清空终端 scrollback（仅在必要时全量重绘，如首次绘制或 resize）。这样内容留在终端 buffer 内，**终端原生选区与复制**可用。
- **输入模型**：底部输入、历史、补全及所有交互式 overlay（session/agent/model picker、设置）由 **prompt_toolkit** 负责。与现有 TUI 共享同一 WebSocket 地址与消息协议（JSON：`message`、`text_delta`、`tool_call_start`/`tool_call_end`、`agent_complete`、`agent_error` 等）。
- **共享**：Gateway 发现逻辑（端口、是否已运行）、WebSocket URL、消息类型与 payload 与现有 attach 模式一致；仅「展示与输入」的实现不同。

---

## 2. 组件

- **行输出层（line renderer）**  
  - 输入：消息列表（user / assistant / system / tool）+ 当前流式缓冲区（未 commit 的 text_delta）+ 终端宽度。  
  - 输出：ANSI 字符串列表（每行一条），每行不超过终端宽度（自动折行）；assistant 消息用 **Rich** 将 Markdown 转为 ANSI 后按行切分。  
  - 策略：平时只追加「新行」（如新消息、新流式行），避免整屏清空；仅在首次绘制或终端 resize 时做全量重绘。

- **流式组装器（stream assembler）**  
  - 与 OpenClaw 的 TuiStreamAssembler 类似：累积 `text_delta` 与可选的 `thinking_delta`；在 `agent_complete` 时把当前缓冲区 commit 为一条 assistant 消息加入消息列表；收到 `tool_call_start` 时追加工具块占位，`tool_call_end` 时补全结果。  
  - 长 token / 凭证类内容不做 mid-token 断行，避免复制时多出空格（可参考 OpenClaw 的 tui-formatters 思路）。

- **输入区**  
  - 使用 **prompt_toolkit** 的多行输入（或 Application 底部一栏）。提交时：以 `/` 开头走 slash 命令（如 `/session`、`/agent`、`/model`、`/help`、`/new`、`/abort`、`/settings`、`/exit`）；以 `!` 开头走本地 shell；否则作为普通消息通过 WebSocket 发送。

- **Picker（session / agent / model）**  
  - 使用 prompt_toolkit 的 full-screen 或 overlay 布局：列表 + 键盘导航 + 选择/取消。列表数据来自 gateway API 或本地配置（与现有 TUI 一致）。选择后发送 session patch / 切换，并更新本地状态，必要时拉取新 history。

- **Header / Footer**  
  - 各占一行：Header 显示连接 URL、当前 agent、session；Footer 显示连接状态、模型、token 等（若 gateway 提供）。作为「内容」的一部分一起按行输出，或在每次更新时用光标移动只重写最后一两行，避免整屏滚动。

---

## 3. 数据流

- **启动**：解析 `tui-native` → 确保 gateway 运行 → 得到 `ws_url` → 建立 WebSocket → 可选拉取 history → 启动 prompt_toolkit 输入循环（或 async 双任务：一个读 WebSocket，一个跑 prompt_toolkit）。
- **用户发消息**：输入区提交 → 若为普通消息则 `ws.send({"type":"message","content":...})`；若为 slash 则本地处理或转发 gateway；若为 `!` 则本地执行 shell 并将结果写入「内容」区。
- **Gateway 下行**：WebSocket 收到 JSON → 按 `type` 分发：`text_delta`/`thinking_delta` 进 stream assembler；`tool_call_start`/`tool_call_end` 更新工具块；`agent_complete` 提交流并刷新消息列表；`agent_error` 显示错误行。每次需要刷新时，由 line renderer 根据当前消息列表 + 流缓冲生成新行，只向 stdout 追加或重写受影响部分，保证不破坏 scrollback。
- **Picker**：用户触发（如 `/session`）→ 从 gateway 或配置取列表 → prompt_toolkit 显示 overlay → 用户选择 → 发送切换请求并更新本地状态 → 关闭 overlay，可选重拉 history 并重绘。

---

## 4. 错误处理

- **WebSocket 断开**：在内容区输出一行如 `[system] Disconnected. Reconnecting...`，并在后台做带退避的重连；重连成功后输出 `[system] Connected.`，可选重拉 history。
- **Gateway 返回错误**：解析失败或 `agent_error` 时，在内容区输出 `[system] Error: ...`，并打日志。
- **终端 resize**：获取新宽高，对当前内容按新宽度重新折行并重绘（或至少重绘 footer）；prompt_toolkit 负责输入区 resize。
- **用户中止**：`/abort` 或 Esc → 向 gateway 发送 abort → 清空当前流状态并输出 `[system] Aborted.`

---

## 5. 测试

- **单元**：  
  - 行渲染器：给定消息列表 + 宽度，输出行列表且每行不超过宽度；assistant Markdown 转 ANSI 后格式正确。  
  - 流式组装器：喂入 text_delta、tool_call_*、agent_complete，最终消息列表与工具块状态符合预期。
- **集成**：Mock WebSocket 服务端发送 text_delta 与 agent_complete；在伪终端或捕获 stdout 下运行 native TUI，断言输出 ANSI 中包含预期文本。
- **手动**：执行 `basket tui-native`，验证连接、发消息、流式输出、在终端中选区复制、以及 session/agent/model picker 与设置行为。

---

## 6. 依赖与入口

- **依赖**：basket-tui 增加 **prompt_toolkit**（可选依赖或必选，由实现决定）。Rich 已存在，用于 Markdown→ANSI。
- **CLI**：在 basket-assistant 的 `main.py` 中识别 `tui-native` 与 `tn`，复用与 `tui` 相同的 gateway 启动与参数（如 `--agent`），然后调用 basket-tui 导出的 `run_tui_native_attach(ws_url, agent_name=..., max_cols=...)`。

---

## 批准与下一步

本设计经 brainstorm 确认后已定稿。实现计划见：**[2026-03-14-tui-native-plan.md](./2026-03-14-tui-native-plan.md)**，按 writing-plans 技能拆分为可执行任务；实现时请使用 superpowers:executing-plans 按任务逐步执行。
