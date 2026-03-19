# basket-capture

录制 TUI 终端会话为 asciinema v2 `.cast` 文件；可选「会话包」模式：按键 sidecar、按动作分目录、可选截图。一条命令、零配置优先。

## 安装

在包目录下安装依赖：

```bash
cd packages/basket-capture
poetry install
```

## 用法

在终端中运行（会启动子进程执行命令并录制其输出到 .cast）：

```bash
# 默认写入 ~/.basket/capture/capture-YYYYMMDD-HHMMSS.cast（自动建目录）
poetry run basket-capture record --command "bash"

# 指定文件或目录
poetry run basket-capture record --output session.cast
poetry run basket-capture record --output ~/my-casts   # 目录内生成带时间戳的 .cast
```

### 会话包模式（`--bundle`）

在 `~/.basket/capture/sessions/session-YYYYMMDD-HHMMSS/` 下生成：

- `session.cast`：整段会话的 asciinema v2
- `input.jsonl`：stdin 侧车日志（`text` / `bytes` / `action_boundary` 等）
- `actions/<seq>_<slug>/meta.json`：每个动作段的起止时间（相对会话秒）与截图列表
- `session_manifest.json`：总览

**动作边界（默认）**：`Ctrl+\`（终端 raw 模式下字节 `0x1C`）结束当前动作并开始下一段；默认**不会**把该字节转发给子进程。需要转发时加 `--forward-action-boundary`。也可用 **`kill -USR1 <recorder-pid>`**（Unix）切分动作。

**截图**：`--screenshot-cmd 'your-script {out_path}'`，在每个动作结束时执行；`{out_path}` 替换为 `actions/.../screenshots/end-*.png`。请自行在脚本里完成「截取当前终端窗口」等平台相关逻辑。

```bash
poetry run basket-capture record --bundle --command "bash"
poetry run basket-capture record --bundle --output ~/my-sessions   # 会话目录建在该路径下
```

### 隐私与安全

`input.jsonl` 可能包含密码或敏感输入；**不要提交到 Git**，仅在可信环境保留。若需最小记录，可后续迭代 `--redact` 类开关（当前版本为完整文本/字节记录策略见 `input.jsonl` 的 `type` 字段）。

## 参数摘要

**单文件 .cast 模式（默认）**

- `--command`：要录制的命令，默认 `bash`
- `--output`：可选。省略时默认为 `~/.basket/capture/capture-YYYYMMDD-HHMMSS.cast`；若传入以 `.cast` 结尾的路径则写入该文件；否则视为目录并在其中生成带时间戳的 `.cast`
- `--timeout`：最大录制秒数，不指定则录到进程退出

**会话包模式（`--bundle`）**

- `--output`：会话根的**父目录**（默认 `~/.basket/capture/sessions/`），其下创建 `session-*`
- `--forward-action-boundary`：把边界字节也发给子 PTY
- `--action-boundary-byte N`：边界字节，支持 `0x1c` 等（默认 `0x1C`）
- `--screenshot-cmd`：动作结束时的截图命令模板

## 文档

- [设计文档](../../docs/plans/2026-03-16-basket-capture-design.md)
- [实现计划](../../docs/plans/2026-03-16-basket-capture-implementation.md)
