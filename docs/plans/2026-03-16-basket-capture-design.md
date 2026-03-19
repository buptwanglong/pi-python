# basket-capture 设计文档

**日期**: 2026-03-16  
**模块名**: basket-capture  
**目的**: 通过录制 OpenClaw TUI 的终端流（与可选截图），自动分析布局与交互，生成 PRD 文档；全自动、小白可上手，首版 PRD 采用纯模板（不引入 AI）。

---

## 一、需求摘要

- **录制/采集**：对 OpenClaw TUI 做屏幕级记录（终端时序 + 可选截图），用素材分析布局、组件、交互。
- **全自动**：录屏/截图进入管道后自动分析并生成 PRD，人工只做触发录制与最终审阅。
- **小白能上手**：我们提供录制工具，一条命令完成「开始录制 → 自动启动目标程序 → 用户操作 → 结束录制 → 自动分析并生成 PRD」。
- **PRD 首版**：选项 A，纯模板填充，不引入 AI；后续可迭代为混合或 AI 增强。

---

## 二、架构（Architecture）

- **模块归属**：monorepo 中新增独立包 `packages/basket-capture`，Python 包名 `basket_capture`。不反向依赖 basket-tui / basket-agent，便于单独测试与复用。
- **流水线三阶段**：
  1. **录制**：CLI 子命令在 pty 中启动用户指定可执行文件（默认 OpenClaw），录制终端时序流并输出 `.cast`；可选在同一会话内按时间或简单启发式触发若干次截图，与 cast 同目录存放并带时间戳或序号。
  2. **分析**：读取 `.cast`，解析为「帧序列 + 输入事件」，用文本/行结构推断布局区域（Header / Chat / Footer / Input）、关键交互点（发送、切换、快捷键），并关联可选截图（按时间戳或序号挂到对应「界面状态」）。
  3. **生成 PRD**：根据分析结果填充 PRD 模板（Markdown），输出到用户指定路径；可选在 PRD 中引用截图路径。首版为纯模板，不调用 LLM。
- **小白体验**：一条命令完成录制 → 自动分析 → 生成 PRD；除可执行路径与输出路径外，零配置或最少配置（如 `basket capture record --auto-generate` 或等价独立命令）。

---

## 三、组件与数据流（Components & data flow）

### 包与 CLI

- 包名：`packages/basket-capture`，`basket_capture`。
- CLI：通过 basket-assistant 挂子命令（如 `basket capture record`、`basket capture generate-prd`），或独立入口 `basket-capture record`（pyproject `scripts`），以「小白一条命令」为准择一或同时支持。

### 录制组件

- **Recorder**：在 pty 中 spawn 用户指定命令（默认 OpenClaw 可执行路径），按 asciinema 兼容格式写 `.cast`（时序 + 文本 + 可选样式）。
- **Screenshot hook（可选）**：同一进程内按间隔或简单规则（如「首帧稳定」「每 N 秒」）触发截图；截图与 cast 同目录，文件名含时间戳/序号；在 cast 的 metadata 或同目录 sidecar 中记录对应时间，供分析阶段关联。
- **会话包（CLI `--bundle`，已实现）**：在 `~/.basket/capture/sessions/session-*/` 下同时产出 `session.cast`、`input.jsonl`（stdin 侧车，**含隐私风险**）、`actions/<seq>_<slug>/meta.json` 与 `session_manifest.json`。动作边界默认为 **`Ctrl+\`（字节 `0x1C`）**；默认不转发给子进程；Unix 上可用 **`SIGUSR1`** 切分。动作结束时可运行用户提供的 `--screenshot-cmd`（`{out_path}` 占位符），截图路径写入对应 `meta.json`。

### 分析组件

- **Cast parser**：读 `.cast`，输出结构化「帧序列」与「输入事件」流。
- **Layout inferrer**：基于行/列与文本模式推断区域（Header / Chat / Footer / Input），输出区域边界（行号或行范围）与类型。
- **Interaction detector**：结合输入事件与帧变化，标记关键交互（发送、切换会话/agent、快捷键等），并与时间戳关联，便于与截图对齐。

### PRD 生成组件（首版：选项 A，无 AI）

- **Template**：Markdown 模板，占位符对应「布局描述」「组件列表」「快捷键/命令」「典型流程」「可选截图引用」。
- **Renderer**：用分析结果填充模板，写出 PRD 文件；若存在截图，在 PRD 中写相对路径或可选内嵌引用。不调用任何 LLM。

### 数据流

- 录制：`用户命令 → Recorder → .cast [+ 截图 + 可选 sidecar]`。
- 分析：`.cast`（+ sidecar）→ Cast parser → 帧/事件流 → Layout inferrer + Interaction detector → 结构化结果（JSON 或内存模型）。
- 生成：结构化结果 + 截图路径列表 → Renderer → PRD Markdown。

---

## 四、错误处理与边界情况

- **录制**：可执行文件不存在或无法 spawn → 明确报错并非 0 退出；pty 不可用（如无 TTY）→ 提示「请在终端中运行」；用户 Ctrl+C 结束 → 正常收尾并保存已录制的 .cast。
- **分析**：.cast 损坏或格式不支持 → 报错并指出文件/行；无法推断布局时 → 仍输出「原始帧/事件」并在 PRD 中标注「布局未识别」；缺少可选截图/sidecar → 仅跳过截图引用，不影响 PRD 生成。
- **PRD 生成**：输出路径不可写 → 报错并退出；模板缺失 → 使用内嵌默认模板或报错（实现时固定一种策略）。

---

## 五、测试策略

- **单元测试**：Cast parser（用 fixture 的 .cast 片段）、Layout inferrer（固定几帧文本）、PRD Renderer（给定结构化输入断言输出 Markdown 片段）。
- **集成测试**：录制 → 分析 → 生成 PRD 的管道，用假命令（如 `echo` / 最小 TUI 脚本）生成 .cast，再跑完整流程并检查 PRD 存在且包含预期章节。
- **首版不要求**：真实启动 OpenClaw 的 E2E；可后续补充。

---

## 六、与现有文档的关系

- 本模块产出的 PRD 可用于指导 basket-tui 的 tui-native 对齐（参考 `docs/plans/2026-03-15-tui-native-openclaw-checklist.md`、`2026-03-15-tui-native-openclaw-ux-plan.md`），或作为独立产品规格留档。

---

**下一步**：使用 writing-plans 技能生成可执行的实现计划（任务拆分、文件与测试清单）。
