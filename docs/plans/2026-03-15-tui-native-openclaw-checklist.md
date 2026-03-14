# tui-native 与 OpenClaw 式 TUI 对照清单

**日期**: 2026-03-15  
**目的**: 先做一份「OpenClaw 式」的完整交互与视觉对照清单，便于后续决定 tui-native 优化优先级。不写代码，仅设计与对照。

**参考**:
- OpenClaw 官方 TUI 文档（布局、快捷键、会话模型）
- 本仓库 `docs/plans/tui-keybindings-and-states.md`（Pi 与 OpenClaw 键位对齐）
- 本仓库 `docs/plans/2026-03-14-tui-native-design.md`（tui-native 现有设计）

---

## 一、整体布局（Layout）

| 区域 | OpenClaw 描述 | tui-native 当前 | 差距 |
|------|----------------|------------------|------|
| **Header** | 一行：连接 URL、当前 agent、当前 session | 启动时输出两行（`[system] Connected...` + `URL=... agent=default session=default`），之后不刷新 | 无固定「Header 行」；切换 session/agent 后未更新展示 |
| **Chat log** | 用户消息、助手回复、系统通知、工具卡片 | 消息通过 line render 按行追加；仅 assistant 最后一条在 agent_complete 时渲染；**工具块未参与渲染** | 工具块未在聊天区展示；无明确「系统通知」样式区分 |
| **Footer** | 连接状态 + agent + session + model + think/verbose/reasoning + token + deliver | 无 | 缺少整条 Footer |
| **Status line** | 连接/运行状态：connecting \| running \| streaming \| idle \| error | 无 | 无状态行 |
| **Input** | 带自动补全的文本编辑 | 单行 prompt_toolkit Buffer，无补全 | 无补全；可考虑多行 |

结论：布局上 tui-native 缺少**固定 Header/Footer/Status** 的语义分区和刷新逻辑，且**工具块未在聊天区渲染**。

---

## 二、消息与流式展示（Message & streaming）

| 项目 | OpenClaw 描述 | tui-native 当前 | 差距 |
|------|----------------|------------------|------|
| 用户消息 | 在 chat log 中展示 | 用户消息由 run 里 put(text) 后，在 consumer 里 append 到 body_lines（需确认是否渲染为 [user]） | 若未走 render，则可能只有纯文本 |
| 助手消息 | Markdown 渲染 | render_messages 对 assistant 用 Rich Markdown | 已有 |
| 流式效果 | 流式打字 | 仅在 agent_complete 时一次性输出整条助手消息，**无逐 token 流式** | 无实时流式显示 |
| 思考过程 | 可显示/隐藏（Ctrl+T） | thinking_delta 进 assembler，未输出到界面 | 未展示；无切换 |
| 工具卡片 | 展示；可展开/折叠（Ctrl+O） | 工具块在 StreamAssembler 中，agent_complete 时只渲染最后一条 assistant，**工具块未渲染** | 工具块未展示；无展开/折叠 |
| 系统通知 | 独立样式 | `[system] ...` 纯文本 | 有，但无统一「系统通知」视觉规范 |
| 代码块 / 长内容 | 可折叠等 | 仅 Rich Markdown 折行 | 无折叠 |

结论：**工具块必须加入渲染**；流式逐 token 输出与思考可见性为体验增强项。

---

## 三、快捷键（Shortcuts）

| 按键 | OpenClaw | tui-native 当前 | 差距 |
|------|----------|------------------|------|
| Enter | 发送消息 | 发送 | 一致 |
| Esc | 中止运行 / 关闭对话框 | 未绑定 | 未实现中止/关闭 |
| Ctrl+C | 清除输入（连续两次退出） | 一次即退出 | 可改为「先清输入，再按退出」 |
| Ctrl+D | 退出 | 退出 | 一致 |
| Ctrl+L | 打开模型选择器 | 未绑定（仅 /model） | 可增加 |
| Ctrl+G | 打开 Agent 选择器 | 未绑定（仅 /agent） | 可增加 |
| Ctrl+P | 打开会话选择器 | 未绑定（仅 /session） | 可增加 |
| Ctrl+O | 展开/折叠工具卡片 | 未绑定 | 工具块未展示故暂无 |
| Ctrl+T | 显示/隐藏思考 | 未绑定 | 思考未展示故暂无 |
| Tab / Shift+Tab | 焦点在区域间切换 | 未实现 | 当前仅输入区可聚焦 |

注：本仓库 `tui-keybindings-and-states.md` 中与 OpenClaw 有部分键位差异（如 Ctrl+G 在 Pi 为「停止 Agent」），若要对齐 OpenClaw 可据此再统一。

结论：优先补 **Esc 中止**、**Ctrl+P/G/L 打开 picker**；Ctrl+O / Ctrl+T 随「工具块展示」「思考展示」一起做。

---

## 四、斜杠命令（Slash commands）

| 命令 | OpenClaw 类 | tui-native 当前 | 差距 |
|------|-------------|------------------|------|
| /help | 有 | 有 | 一致 |
| /exit | 有 | 有 | 一致 |
| /session | 有 | 有（picker） | 一致 |
| /new | 新建会话（隔离） | 有（new_session） | 一致 |
| /reset | 重置当前会话 | 无 | 可选 |
| /agent | 有 | 有（picker） | 一致 |
| /model | 有 | 有（picker；当前误用 switch_agent 需修） | 实现需核对 |
| /abort | 有 | 有 | 一致 |
| /settings | 有 | 仅 stub | 需实现 |
| /deliver, /think, /reasoning, /verbose | 有 | 无 | 可选 |
| /status | 有 | 无 | 可选 |

结论：/settings 与 /model 行为需补齐或修正；其余为增强项。

---

## 五、会话与上下文（Sessions）

| 项目 | OpenClaw 描述 | tui-native 当前 | 差距 |
|------|----------------|------------------|------|
| 会话模型 | agent::session 键；按 agent 多会话 | 由 gateway 管理；本地有 switch_session | 概念对齐即可 |
| 会话列表 | 选择器展示 | Session picker 有 | 有 |
| 切换后更新 | Header 显示当前 session/agent | 仅发 switch 请求，界面未刷新 Header 文案 | 需在 UI 刷新当前 session/agent 显示 |

结论：切换 session/agent 后需**更新 Header（或等效一行）**。

---

## 六、状态与阶段（Phase / Status）

| 状态 | OpenClaw / Pi 文档 | tui-native 当前 | 差距 |
|------|--------------------|------------------|------|
| connecting | 连接中 | 有 ready_event，无文案 | 可显示 "Connecting..." |
| running / streaming / idle | 运行/流式/空闲 | 无展示 | 无状态行 |
| error | 错误 | 仅 [system] 文本 | 可纳入状态行 |
| 连接状态 | 独立于 phase | 未区分 | Footer/Status 可带连接状态 |

结论：需要**状态行或 Footer 中一段**表示 phase + 连接状态。

---

## 七、其他交互

| 项目 | OpenClaw 描述 | tui-native 当前 | 差距 |
|------|----------------|------------------|------|
| 输入区自动补全 | 有 | 无 | 无 |
| 多行输入 | 支持 | 当前单行 | 可做多行 |
| 焦点循环 | Tab 切换区域 | 仅输入区 | 可选 |
| 清屏 | Ctrl+Shift+L（Pi 文档） | 无 | 可选 |
| 滚动到底部 | Ctrl+End（Pi 文档） | 无 | 可选（终端原生可滚则未必必要） |

---

## 八、优先级建议（供后续拍板）

按「补齐基础体验 → 对齐 OpenClaw 常用 → 增强」粗分：

1. **P0（必须）**
   - 工具块参与渲染并在聊天区展示（当前完全缺失）。
   - 固定 Header 行（URL + agent + session）并在切换后刷新。
   - 固定 Footer 或 Status 行（至少：连接状态 + 当前 phase/ idle|streaming|error）。

2. **P1（强烈建议）**
   - Esc 中止当前轮次。
   - Ctrl+P / Ctrl+G / Ctrl+L 打开 session/agent/model picker。
   - /settings 实现（至少部分选项）。
   - 修复 /model 语义（若 gateway 支持 switch_model，勿用 switch_agent）。

3. **P2（体验增强）**
   - 流式逐 token 输出（在保留终端可复制前提下）。
   - 思考内容可显示/隐藏（Ctrl+T）并参与渲染。
   - 工具块可展开/折叠（Ctrl+O）。
   - 状态阶段细化（waiting_model / thinking / tool_running 等）在 Footer/Status 展示。
   - Ctrl+C 改为「先清空输入，第二次再退出」。

4. **P3（可选）**
   - 输入区补全、多行输入、/deliver /think 等、Tab 焦点循环、/status、/reset。

---

## 九、设计确认与下一步

**设计确认（2026-03-15）**：以上对照清单及 P0/P1/P2/P3 优先级已获同意，作为「tui-native 展示与交互优化」的正式设计依据。

**实现计划**：见 `docs/plans/2026-03-15-tui-native-openclaw-ux-plan.md`，按 P0 → P1 拆分为可执行任务；执行时使用 superpowers:executing-plans 按任务逐步实施。
