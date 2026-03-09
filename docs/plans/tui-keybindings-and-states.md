# TUI 快捷键与状态规范

**日期**: 2025-03-08  
**范围**: basket-tui 与 OpenClaw TUI 对齐的快捷键表、状态/阶段语义、术语映射。供六阶段实现时统一遵守，不单独改键位。

---

## 一、快捷键表（目标与 OpenClaw 对应）

| 按键 | OpenClaw 功能 | Pi TUI 目标功能 | 备注 |
|------|----------------|------------------|------|
| Enter | 发送消息 | 发送消息 | 保持 |
| Esc | 中止操作 / 关闭对话框 | 清空输入或关闭模态；运行中弹出中止确认 | 阶段 2 实现 |
| Ctrl+C | 清除输入（连续两次退出） | 保持；连续两次退出可后续加 | 保持 |
| Ctrl+D | 直接退出 | 切换深色模式（当前）；退出可另键 | 保持 |
| Ctrl+L | 打开模型选择器 | **模型信息/选择**（Clear 改为 Ctrl+Shift+L） | 阶段 4 |
| Ctrl+G | 打开 Agent 选择器 | **停止 Agent**（保留）；Agent 选择用 /agents | 保持 |
| Ctrl+P | 打开会话选择器 | **会话选择器**（Plan 改为 Ctrl+Shift+P 或 /plan） | 阶段 4 |
| Ctrl+Shift+L | — | **清屏**（原 Ctrl+L） | 阶段 1 后改 |
| Ctrl+Shift+P | — | **Plan 模式**（原 Ctrl+P） | 阶段 4 改 |
| Ctrl+O | 展开/折叠工具卡片 | 切换最后一条工具卡片展开状态 | 阶段 3 |
| Ctrl+T | 显示/隐藏思考过程 | Todo 展开/折叠（保持）；思考显示可 /think | 保持 |
| Ctrl+Shift+T | — | 转录 overlay | 保持 |
| Ctrl+E | — | 展开最后工具结果 | 保持 |
| Ctrl+End | — | 滚动到底部 | 保持 |
| Tab | 切换焦点区域 | 下一焦点区（Header→消息区→输入区→状态栏→Header） | 阶段 2 |
| Shift+Tab | 上一焦点 | 上一焦点区 | 阶段 2 |
| Ctrl+PgUp | — | 焦点到消息区 | 阶段 2 |
| Ctrl+PgDown | — | 焦点到输入区 | 阶段 2 |
| Page Up/Down | 消息区滚动 | 保持 | 保持 |
| Q | — | 退出 | 保持 |

---

## 二、状态与阶段

### 2.1 对话阶段（AppState.phase）

沿用现有枚举，用于状态栏与逻辑分支：

- **idle** — 就绪，无运行中任务
- **waiting_model** — 已提交，等待模型首 token
- **thinking** — 思考中（thinking_delta）
- **streaming** — 流式输出（text_delta）
- **tool_running** — 工具执行中
- **error** — 本轮出错

与 OpenClaw 的「连接状态」独立：若未来支持 attach/relay，可增加**连接状态**枚举（connecting / connected / idle / error），用于 Header 圆点与状态栏第一列。

### 2.2 连接状态（预留）

- **connecting** — 连接中
- **connected** — 已连接
- **idle** — 空闲
- **error** — 错误

当前单机无 Gateway 时，可视为固定「本地」+ connected；attach 模式再接入真实状态。

---

## 三、术语映射

| Pi 代码/配置 | 文档/UI 文案 | 说明 |
|--------------|----------------|------|
| coding_agent | Agent | 当前与单个 Agent 交互 |
| session_id / _session_id | Session / 会话 | 会话标识符 |
| session_manager | — | SessionManager 列表/创建/加载会话 |
| output_blocks / output_blocks_with_role | 消息列表 / Chat Log | 已提交消息块 |
| streaming_buffer | 当前流式块 | 未 finalize 的助手内容 |

多 Agent / 多 Session 扩展时，命名与文案与此表一致。

---

## 四、引用

- 实现规划：TUI 六阶段实现规划（阶段 0–5）
- 状态分析：`docs/plans/2025-03-08-tui-state-analysis-and-improvements.md`
- OpenClaw 参考：OpenClaw TUI 产品交互文档
