# basket-capture

录制 TUI 终端会话为 asciinema v2 `.cast`，自动分析布局与交互，用纯模板生成 PRD 文档。一条命令、零配置优先，小白可上手。

## 安装

在包目录下安装依赖：

```bash
cd packages/basket-capture
poetry install
```

## 用法

**录制**（在终端中运行，会启动子进程执行命令并录制其输出）：

```bash
poetry run basket-capture record --command "openclaw" --output session.cast --auto-generate
```

`--auto-generate` 表示录制结束后自动对生成的 cast 跑 `generate-prd` 并写出 PRD。

**仅从已有 cast 生成 PRD：**

```bash
poetry run basket-capture generate-prd --cast session.cast --output PRD.md
```

不指定 `--output` 时，默认在与 cast 同目录下生成 `<cast 文件名>_prd.md`。

## 文档

- [设计文档](../../docs/plans/2026-03-16-basket-capture-design.md)
- [实现计划](../../docs/plans/2026-03-16-basket-capture-implementation.md)
