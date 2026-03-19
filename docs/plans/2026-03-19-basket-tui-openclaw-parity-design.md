# Basket Native TUI — OpenClaw 录制对标（视觉 A + 交互 B）

> **依据**：`~/.basket/capture/sessions/session-20260319-200048` 内《OpenClaw TUI 交互与设计文档》及会话产物（cast / input.jsonl / manifest）。  
> **状态**：已通过 brainstorming 确认（2026-03-19）。  
> **范围**：默认 `basket tui` 路径 — `basket-tui` **native**（`prompt_toolkit` + gateway WebSocket），非旧版 Textual 全屏应用（除非后续单独立项）。

---

## 1. 目标

| 维度 | 目标 |
|------|------|
| **A 视觉与信息架构** | 高保真对标录制：橙色系主色、横幅层次、Unicode 画线分区、顶栏 chrome、底栏密度与文档一致；产品名仍为 **Basket**。 |
| **B 交互与安全** | 底栏展示 `running` / `streaming` 等与连接状态组合，**带耗时秒数**与 **spinner**；**首次 Ctrl+C 仅提示再按一次，第二次才退出**；`Esc` / `/abort` 仍表示中止当前轮（与退出解耦）。 |
| **Doctor 面板** | **第一版仅 TUI 本地启发式**（不新增 gateway 结构化 warning 协议）：在可检测问题时显示带框面板；无问题时不占位或折叠。 |

---

## 2. 方案结论（混合 / 推荐）

- **视觉与高保真布局**主要在 **`basket_tui/native`** 完成（`layout.py`、`run.py`、必要时 `pipeline/render.py` 或小型 `ui/theme.py`）。
- **动态摘要**（agent / session / phase 等）继续依赖 **现有 WebSocket 处理链**（`make_handlers`、`ui_state`、`header_state`）；**模型名、token、verbose** 等若当前消息中不可得，第一版允许 **`?` / 省略**，后续再以独立迭代补 gateway 字段（不阻塞本期）。
- **Doctor** 不依赖服务端：由 TUI 在启动或连接阶段运行轻量检查（例如 gateway 连接失败/超时、可选的本地路径提示），将结果写入 `doctor_lines: list[str]` 或等价状态，有内容则渲染边框面板。

---

## 3. 信息架构（IA）

自上而下（与录制文档对齐）：

1. **启动层**：品牌横幅（主色标题 + 版本 + 标语一行）。版本建议 `importlib.metadata.version("basket-tui")` 或 `basket-assistant`（以实际入口包为准）。
2. **Doctor 层**（条件）：迁移/环境类提示，Unicode 线框；无内容则不显示。
3. **会话 chrome 层**：URL、agent、session；扩展槽位留给 model / tokens / verbose（有数据再显示）。
4. **对话与工具输出层**：现有流式 ANSI body（`body_lines`）；保持与 gateway 输出一致。
5. **状态条**：spinner + `running|streaming|idle` + `• {elapsed}s` + `| connected|connecting|…`。
6. **分隔 + 输入行**：保留 `❯` 与 `BufferControl` 输入区。

---

## 4. 交互与状态机

### 4.1 底栏计时

- 当 `ui_state["phase"]` 从 `idle` 进入 `running` 或 `streaming`（以现有 handler 为准）时，记录 **单调时钟起点**（`time.monotonic()`）。
- 底栏文案每秒或随 `invalidate` 更新展示 **整数秒**（与录制中 `running • {N}s` 一致）。
- Spinner 字符序列与录制一致或等价：`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`（周期循环）。

### 4.2 双击 Ctrl+C 退出

- **第一次** `Ctrl+C`：设置 `exit_pending=True`，底栏或系统行提示 `press ctrl+c again to exit`（英文或中英一致策略需在实现计划中固定）。
- **第二次**：执行现有 `_do_exit()` 路径（`conn.close()` + `app.exit()`）。
- **可选**：若 N 秒内无第二次，自动清除 `exit_pending`（避免永久卡住；N 默认 5–10s，可配置为不设超时）。
- `Ctrl+D` 策略：与录制对齐时建议 **与 Ctrl+C 相同**（双击确认）；或在设计实现计划中明确「单次退出」— **本设计推荐与 Ctrl+C 一致双击**，降低误触。

### 4.3 Esc / `/abort`

- 保持 **仅中止当前轮**，不触发退出确认状态机。

---

## 5. 视觉规范（高保真）

- **主色**：ANSI 24-bit 橙色系，接近录制描述（如标题约 `38;2;255;90;45`、次要 `38;2;255;138;91`）；次要信息灰系 `38;2;139;127;119` 等。
- **画线**：面板使用 `│─└┘┌┐` 等 Unicode；横向分隔与现有 `─` 行协调。
- **OSC 8**：若 body 中已有链接序列，终端能力允许则保留；不在第一版强制改造 gateway 输出。

---

## 6. 测试策略

- **单元测试**：底栏字符串格式化（含 phase、connection、elapsed、spinner 索引）；双击 Ctrl+C 状态机（纯函数或小型类 + mock）；Doctor 启发式在给定环境下的输出列表。
- **回归**：现有 `tests/native/test_layout.py`、`test_run.py`、`test_handlers.py` 等需随布局高度/窗口数量更新。
- **E2E**：可选；第一版以组件与状态机测试为主。

---

## 7. 非目标（本期不做）

- Gateway 下发结构化 Doctor / chrome（留待后续迭代）。
- Textual 旧 TUI 对齐（除非单独需求）。
- 与 OpenClaw 端口/文案 1:1（仍为 Basket + 本仓库 gateway 端口约定）。

---

## 8. 相关文档

- `docs/plans/2026-03-14-tui-native-design.md`
- `docs/plans/2026-03-15-tui-native-openclaw-ux-plan.md`
- `docs/plans/2026-03-19-basket-tui-openclaw-parity-implementation.md`（实现任务拆解）

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-03-19 | 初版：brainstorming 定稿 + Doctor v1 本地启发式 + 混合方案确认 |
