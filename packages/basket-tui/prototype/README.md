# Pi TUI 原型（HTML + CSS）

本目录是 **pi-tui** 的静态原型，用于在浏览器中预览「Claude Code 式」的布局与样式，与 TUI 实现沟通一致后再转成 Textual TCSS + 组件。

## 如何查看

在浏览器中直接打开 `index.html`，或本地起一个静态服务：

```bash
# 在 prototype 目录下
cd packages/pi-tui/prototype
python3 -m http.server 8080
# 打开 http://localhost:8080
```

## 内容说明

- **index.html**：一屏示例对话，包含：
  - 用户消息、助手首段；
  - **Claude Code 风格工具块**：紧凑一行 `▶ Bash(ls -la)` / `⏺ Bash(npm root -g)`，状态行「Running…」或「⎿ Interrupted · What should Claude do instead?」；
  - 助手总结（含代码块）、输入区。
- **styles.css**：样式与 `basket_tui/styles/app.tcss` 语义对应（`.message-user`、`.message-assistant`、`.tool-block`、`.tool-block--claude` 等），便于后续迁移到 TUI。

## 与 TUI 的对应

| 原型 class / id   | TUI (app.tcss)        |
|-------------------|------------------------|
| `#output-container` | `#output-container`  |
| `#output`         | `#output`              |
| `#input`          | `#input`               |
| `.message-user`   | `.message-user`        |
| `.message-assistant` | `.message-assistant` |
| `.message-system`  | `.message-system`     |
| `.tool-block`      | `.tool-block`         |
| `.tool-block--claude` | Claude Code 风格：紧凑工具名(参数) + 状态（Running/Interrupted） |
| `.code-block`      | 助手 Markdown 内代码块 |

调色、间距、边框等在 `styles.css` 的 `:root` 和对应选择器中修改；确认后再同步到 Textual 的 TCSS 与主题。
