# Basket-TUI 日志配置说明

## 日志输出位置

**默认配置**：日志只写入文件，不显示在 TUI 界面

- **日志文件位置**：`~/.basket/logs/basket.log`
- **文件轮转**：单个文件最大 10MB，保留 5 个备份（总共 ~50MB）
- **编码**：UTF-8

## 日志级别控制

日志级别按优先级从高到低：

1. **环境变量 `BASKET_LOG_LEVEL`**（全局，影响所有 basket 模块）
   ```bash
   export BASKET_LOG_LEVEL=DEBUG
   poetry run basket tui
   ```

2. **环境变量 `BASKET_TUI_LOG_LEVEL`**（仅影响 basket-tui，向后兼容）
   ```bash
   export BASKET_TUI_LOG_LEVEL=INFO
   poetry run basket tui
   ```

3. **配置文件 `~/.basket/settings.json`**
   ```json
   {
     "log_level": "DEBUG"
   }
   ```

4. **默认级别**：`INFO`

可用级别：`DEBUG` | `INFO` | `WARNING` | `ERROR`

## 查看日志

### 实时查看日志
```bash
tail -f ~/.basket/logs/basket.log
```

### 查看最近日志
```bash
tail -n 100 ~/.basket/logs/basket.log
```

### 搜索特定内容
```bash
grep "ERROR" ~/.basket/logs/basket.log
grep "WebSocket" ~/.basket/logs/basket.log
```

### 查看调试日志
```bash
# 临时设置 DEBUG 级别
BASKET_LOG_LEVEL=DEBUG poetry run basket tui

# 然后在另一个终端查看
tail -f ~/.basket/logs/basket.log
```

## 控制台输出（可选）

如果需要同时在控制台（stderr）看到日志（调试用）：

```bash
export BASKET_LOG_TO_CONSOLE=1
poetry run basket tui
```

**注意**：TUI 模式下，控制台输出会干扰界面显示，建议只在需要调试时开启。

## 日志格式

```
[2026-03-15 22:52:22] [INFO    ] [basket_tui.client:45] WebSocket connected
```

格式说明：
- `时间戳`：精确到秒
- `级别`：8 字符对齐（DEBUG/INFO/WARNING/ERROR）
- `位置`：模块名:行号
- `消息`：具体日志内容

## 清理日志

日志文件会自动轮转，但如果需要手动清理：

```bash
# 查看日志文件大小
du -h ~/.basket/logs/

# 清理所有日志
rm ~/.basket/logs/basket.log*

# 只保留当前日志文件
rm ~/.basket/logs/basket.log.?
```

## 常见问题

### Q: 日志没有生成？

检查日志目录权限：
```bash
ls -la ~/.basket/logs/
```

### Q: 日志文件太大？

日志会自动轮转，单个文件最大 10MB。如果仍然太大，可以调整配置或手动清理旧日志。

### Q: 如何禁用日志？

设置级别为 ERROR 或更高：
```bash
export BASKET_LOG_LEVEL=ERROR
```

或在 settings.json 中：
```json
{
  "log_level": "ERROR"
}
```

### Q: 如何在 TUI 界面看到日志？

日志设计为后台记录，不显示在 TUI 界面。如需查看，请使用 `tail -f ~/.basket/logs/basket.log`。
