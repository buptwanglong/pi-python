# basket-capture 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增独立包 basket-capture：在 pty 中录制 OpenClaw（或任意 TUI）终端流为 .cast，自动分析布局与交互，用纯模板生成 PRD；一条命令、零配置优先，小白可上手。

**Architecture:** 三阶段管道：Recorder(pty → .cast) → Analyzer(cast parser + layout inferrer + interaction detector) → PRD Renderer(模板填充)。包独立于 basket-tui/basket-agent；CLI 可独立（basket-capture）或挂到 basket（basket capture）。首版不引入 AI，截图 hook 为可选后续任务。

**Tech Stack:** Python 3.12+, 标准库 pty/termios（或 asciinema 兼容库）、Pydantic v2、Markdown 模板；测试 pytest + pytest-asyncio。

**设计依据:** `docs/plans/2026-03-16-basket-capture-design.md`

---

## Phase 1：包脚手架与 Cast 解析

### Task 1: 创建 basket-capture 包结构

**Files:**
- Create: `packages/basket-capture/pyproject.toml`
- Create: `packages/basket-capture/basket_capture/__init__.py`
- Create: `packages/basket-capture/README.md`

**Step 1: 添加 pyproject.toml**

新建 `packages/basket-capture/pyproject.toml`，内容：

```toml
[tool.poetry]
name = "basket-capture"
version = "0.1.0"
description = "Record TUI terminal sessions and generate PRD from cast"
authors = ["Pi Python Team"]
readme = "README.md"
packages = [{include = "basket_capture"}]
classifiers = [
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
]

[tool.poetry.dependencies]
python = "^3.12"
pydantic = "^2.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"

[tool.poetry.scripts]
basket-capture = "basket_capture.cli:main"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

**Step 2: 添加包占位与 README**

- `basket_capture/__init__.py` 仅含 `__version__ = "0.1.0"`。
- `README.md` 简要说明：录制 TUI 生成 .cast，分析后生成 PRD；用法见设计文档。

**Step 3: 安装包**

Run: `cd packages/basket-capture && poetry install`  
Expected: 成功，无错误。

**Step 4: Commit**

```bash
git add packages/basket-capture/
git commit -m "chore(basket-capture): add package scaffold"
```

---

### Task 2: Cast 解析器（asciinema 兼容格式）

**Files:**
- Create: `packages/basket-capture/basket_capture/cast.py`
- Create: `packages/basket-capture/tests/__init__.py`
- Create: `packages/basket-capture/tests/fixtures/sample.cast`
- Create: `packages/basket-capture/tests/test_cast.py`

**Step 1: 添加 sample.cast fixture**

asciinema v2 格式为 JSON：`{"version": 2, "width": 80, "height": 24, "timestamp": 1234567890, "env": {}, "title": "", "stdout": [[0.1, "hello"], [0.2, " world\n"]]}`。  
新建 `tests/fixtures/sample.cast`，内容为上述单行 JSON（width=80, height=24，stdout 若干 [delay, text]）。

**Step 2: 写解析失败测试**

在 `tests/test_cast.py` 中：
- `test_parse_cast_returns_frames_and_events()`：调用 `parse_cast(path)`，断言返回结构包含 `frames`（列表）和 `events`（列表）；用 `tests/fixtures/sample.cast`。
- `test_parse_cast_invalid_file_raises()`：对不存在的路径断言抛出（如 `FileNotFoundError` 或自定义异常）。

**Step 3: 运行测试，确认失败**

Run: `cd packages/basket-capture && poetry run pytest tests/test_cast.py -v`  
Expected: FAIL（parse_cast 未定义或 fixture 未就绪）。

**Step 4: 实现 parse_cast**

在 `basket_capture/cast.py` 中实现 `parse_cast(path: str | Path) -> CastResult`（或等价命名）：
- 读取 JSON，解析 `version`、`width`、`height`、`stdout`。
- 将 `stdout` 转为「帧」序列（按时间戳累积文本，每行一个逻辑帧或按 delta 分帧，以设计为准）；输入事件在 asciinema 中常无单独字段，首版可返回空 `events` 或从 stdin 若存在则解析。
- 返回 Pydantic 模型或 dataclass：`frames`（含 time、lines/text）、`events`、`width`、`height`。

**Step 5: 运行测试，确认通过**

Run: `cd packages/basket-capture && poetry run pytest tests/test_cast.py -v`  
Expected: PASS.

**Step 6: Commit**

```bash
git add packages/basket-capture/basket_capture/cast.py packages/basket-capture/tests/
git commit -m "feat(basket-capture): add cast parser for asciinema v2 format"
```

---

## Phase 2：布局推断与交互检测

### Task 3: Layout inferrer（从帧推断区域）

**Files:**
- Create: `packages/basket-capture/basket_capture/layout.py`
- Create: `packages/basket-capture/tests/test_layout.py`

**Step 1: 写失败测试**

- `test_infer_regions_returns_header_chat_footer_input()`：给定一个固定多行文本（模拟 TUI 一帧：首行像 header，中间多行 chat，末行像 footer，最后为 input 行），调用 `infer_regions(frames)` 或单帧接口，断言返回区域列表，至少包含类型 Header/Chat/Footer/Input 中的若干项及行范围。

**Step 2: 运行测试，确认失败**

Run: `cd packages/basket-capture && poetry run pytest tests/test_layout.py -v`  
Expected: FAIL.

**Step 3: 实现 infer_regions**

在 `layout.py` 中：基于行内容启发式（如首行含 URL/agent、末行含状态、最后一行可编辑区等）或固定行数分配，输出 `List[Region]`（Region 含 type、start_line、end_line）。可先做简单规则（首行=Header，末行=Footer，中间=Chat，再识别 Input）。

**Step 4: 运行测试，确认通过**

Run: `cd packages/basket-capture && poetry run pytest tests/test_layout.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/basket-capture/basket_capture/layout.py packages/basket-capture/tests/test_layout.py
git commit -m "feat(basket-capture): add layout inferrer for Header/Chat/Footer/Input"
```

---

### Task 4: Interaction detector（占位 + 事件关联）

**Files:**
- Create: `packages/basket-capture/basket_capture/interactions.py`
- Create: `packages/basket-capture/tests/test_interactions.py`

**Step 1: 写失败测试**

- `test_detect_returns_list_of_events()`：给定 cast 解析结果（含 frames/events），调用 `detect_interactions(parsed)`，断言返回列表，元素含时间戳和类型（如 send、switch_session 等）；若 cast 无输入事件，可返回空列表但结构正确。

**Step 2: 运行测试，确认失败**

Run: `cd packages/basket-capture && poetry run pytest tests/test_interactions.py -v`  
Expected: FAIL.

**Step 3: 实现 detect_interactions**

在 `interactions.py` 中：遍历解析后的事件（若有 stdin 或 key 事件）或基于帧间文本变化做简单启发（如新行出现、某行从空变非空），输出 `List[Interaction]`（timestamp、type、可选 payload）。首版可只做「占位」：有事件则映射，无则返回空列表。

**Step 4: 运行测试，确认通过**

Run: `cd packages/basket-capture && poetry run pytest tests/test_interactions.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add packages/basket-capture/basket_capture/interactions.py packages/basket-capture/tests/test_interactions.py
git commit -m "feat(basket-capture): add interaction detector (placeholder)"
```

---

## Phase 3：PRD 模板与渲染

### Task 5: PRD 模板与 Renderer（纯模板，无 AI）

**Files:**
- Create: `packages/basket-capture/basket_capture/prd_template.md`
- Create: `packages/basket-capture/basket_capture/renderer.py`
- Create: `packages/basket-capture/tests/test_renderer.py`

**Step 1: 添加 PRD 模板**

在 `basket_capture/prd_template.md` 中写 Markdown，占位符用 `{{layout}}`、`{{components}}`、`{{shortcuts}}`、`{{flows}}`、`{{screenshots}}` 等（或统一用 `{{section_name}}`），与 Renderer 约定一致。

**Step 2: 写失败测试**

- `test_render_prd_produces_markdown_with_sections()`：构造分析结果（layout regions、interactions、可选 screenshot paths），调用 `render_prd(analysis_result, output_path=None)`，断言返回或写入的字符串包含预期章节标题及占位符被替换（无 `{{` 残留）。

**Step 3: 运行测试，确认失败**

Run: `cd packages/basket-capture && poetry run pytest tests/test_renderer.py -v`  
Expected: FAIL.

**Step 4: 实现 render_prd**

在 `renderer.py` 中：读取内嵌或同目录 `prd_template.md`，用分析结果（layout、interactions、screenshots）填充占位符，返回 Markdown 字符串；若传入 `output_path` 则写入文件。不做任何 LLM 调用。

**Step 5: 运行测试，确认通过**

Run: `cd packages/basket-capture && poetry run pytest tests/test_renderer.py -v`  
Expected: PASS.

**Step 6: Commit**

```bash
git add packages/basket-capture/basket_capture/prd_template.md packages/basket-capture/basket_capture/renderer.py packages/basket-capture/tests/test_renderer.py
git commit -m "feat(basket-capture): add PRD template and renderer (no AI)"
```

---

## Phase 4：录制器与 CLI

### Task 6: Recorder（pty 录制为 .cast）

**Files:**
- Create: `packages/basket-capture/basket_capture/recorder.py`
- Create: `packages/basket-capture/tests/test_recorder.py`

**Step 1: 写失败测试**

- `test_record_produces_cast_file()`：在测试中用假命令（如 `echo "hello"` 或 `sleep 0.1`）调用 `record(command, output_path, timeout=2)`，断言 output_path 存在且为合法 JSON，包含 `version`、`stdout`。

**Step 2: 运行测试，确认失败**

Run: `cd packages/basket-capture && poetry run pytest tests/test_recorder.py -v`  
Expected: FAIL（或 skip 若需 TTY）。

**Step 3: 实现 record**

在 `recorder.py` 中：使用 `pty.fork()` 或 `subprocess` + pty 在子进程中执行 `command`，捕获 stdout 与时间戳，按 asciinema v2 格式写入 `output_path`。处理 SIGINT 以正常结束并保存。无 TTY 时测试可标记 `@pytest.mark.skipif(not sys.stdin.isatty())` 或使用伪 pty 库（如 `pexpect` 可选依赖）。

**Step 4: 运行测试，确认通过**

Run: `cd packages/basket-capture && poetry run pytest tests/test_recorder.py -v`  
Expected: PASS（或 skip 在无 TTY 环境）。

**Step 5: Commit**

```bash
git add packages/basket-capture/basket_capture/recorder.py packages/basket-capture/tests/test_recorder.py
git commit -m "feat(basket-capture): add pty recorder writing asciinema v2 .cast"
```

---

### Task 7: CLI（record + generate-prd，一条命令）

**Files:**
- Create: `packages/basket-capture/basket_capture/cli.py`
- Modify: `packages/basket-capture/basket_capture/__init__.py`（可选导出）

**Step 1: 实现 CLI 骨架**

在 `cli.py` 中实现 `main()`：
- 子命令 `record`：`--command`（默认可配置为 openclaw 或 `bash`）、`--output`（.cast 路径）、`--auto-generate`（录完后自动调 generate-prd）。
- 子命令 `generate-prd`：`--cast`（.cast 文件）、`--output`（PRD 输出路径）。
- 使用 `argparse` 或 `typer`。`record` 调用 `recorder.record()`；`generate-prd` 调用 `parse_cast` → layout inferrer → interaction detector → render_prd。

**Step 2: 手动验证**

Run: `cd packages/basket-capture && poetry run basket-capture generate-prd --cast tests/fixtures/sample.cast --output /tmp/out-prd.md`  
Expected: 生成 `/tmp/out-prd.md`，内容含预期章节。

Run: `cd packages/basket-capture && poetry run basket-capture record --command "echo hi" --output /tmp/test.cast --auto-generate`（或仅 record 不 auto-generate）  
Expected: 生成 /tmp/test.cast；若 --auto-generate 则再生成 PRD（输出路径可默认当前目录或与 cast 同目录）。

**Step 3: 集成测试（可选）**

在 `tests/test_integration.py` 中：端到端 `generate-prd` 用 fixture cast，断言输出文件存在且包含 "Layout" 或 "PRD" 等关键字。

**Step 4: Commit**

```bash
git add packages/basket-capture/basket_capture/cli.py tests/test_integration.py
git commit -m "feat(basket-capture): add CLI record + generate-prd with --auto-generate"
```

---

## Phase 5：错误处理与文档收尾

### Task 8: 错误处理（录制/分析/生成）

**Files:**
- Modify: `packages/basket-capture/basket_capture/recorder.py`
- Modify: `packages/basket-capture/basket_capture/cast.py`
- Modify: `packages/basket-capture/basket_capture/cli.py`

**Step 1: 录制阶段**

- 可执行文件不存在或 spawn 失败：在 `recorder.record()` 中捕获，打印明确错误信息，退出码非 0。
- 无 TTY：检测并提示「请在终端中运行」，退出码非 0。
- Ctrl+C：捕获 KeyboardInterrupt，保存已录制 .cast 后退出。

**Step 2: 分析阶段**

- .cast 损坏或非 JSON：在 `parse_cast` 中抛出清晰异常；CLI 捕获并打印文件/行信息。
- 无法推断布局：Layout inferrer 返回空或部分区域；PRD 中标注「布局未识别」而不崩溃。

**Step 3: PRD 生成阶段**

- 输出路径不可写：CLI 捕获并报错退出。
- 模板缺失：使用内嵌默认模板（将 prd_template.md 内容嵌入为字符串常量或 importlib.resources）。

**Step 4: 为上述情况添加或补充测试**

至少覆盖：无效 cast 路径、无效输出路径。

**Step 5: Commit**

```bash
git add packages/basket-capture/basket_capture/
git commit -m "fix(basket-capture): error handling for record/parse/render and CLI"
```

---

### Task 9: README 与设计文档引用

**Files:**
- Modify: `packages/basket-capture/README.md`
- 可选: `docs/plans/2026-03-16-basket-capture-design.md`（已存在，可加「实现计划」链接）

**Step 1: 更新 README**

- 说明用途：录制 TUI 生成 PRD。
- 安装：`poetry install`（在 packages/basket-capture）。
- 用法：`basket-capture record --command "openclaw" --output session.cast --auto-generate`；`basket-capture generate-prd --cast session.cast --output PRD.md`。
- 指向设计文档与实现计划。

**Step 2: Commit**

```bash
git add packages/basket-capture/README.md
git commit -m "docs(basket-capture): README usage and links to design/plan"
```

---

## 可选后续（不纳入本计划必做）

- **Screenshot hook**：录制时按间隔或规则截图，写 sidecar 与 cast 关联；分析/PRD 中引用截图。
- **挂到 basket**：在 basket-assistant 中依赖 basket-capture（optional），注册 `basket capture record` / `basket capture generate-prd`。
- **E2E**：真实启动 OpenClaw 的端到端测试（需环境中有 OpenClaw）。

---

**Plan complete and saved to `docs/plans/2026-03-16-basket-capture-implementation.md`.**

**执行方式二选一：**

**1. Subagent-Driven（本会话）** — 按任务派发子 agent，每步完成后你做 review，再进入下一步，迭代快。

**2. Parallel Session（新会话）** — 在新会话（建议在 worktree）中打开，用 executing-plans 技能按计划批量执行，在检查点做 review。

你选哪种？
