# TUI Mode E2E 测试场景文档

## 概述

本文档定义了 Pi Coding Agent TUI 模式的端到端测试场景。TUI 模式使用 Textual 框架提供交互式文本用户界面。

## TUI 模式特点

### 核心功能
- 实时流式显示 LLM 响应
- 工具执行可视化（开始/结束/结果）
- Markdown 渲染和语法高亮
- 多轮对话上下文保持
- 错误信息清晰展示

### 关键组件
- `basket_assistant/modes/tui.py` - TUI 模式入口和事件处理
- `basket_tui/basket_tui/app.py` - Textual 应用主体
- `basket_tui/basket_tui/components/streaming_log.py` - 流式消息显示组件

### 事件流程
```
用户输入 → handle_user_input()
  → agent.run(stream_llm_events=True)  （与 TUI 同一 asyncio 事件循环）
  → 触发事件：
    - text_delta: 文本流式输出
    - thinking_delta: 思考过程
    - agent_tool_call_start: 工具开始执行
    - agent_tool_call_end: 工具执行完成
    - agent_turn_complete: 轮次完成
    - agent_error: 错误发生
  → 在 app 线程内直接调用 app 方法更新 UI（不可用 call_from_thread，否则会报错）
```

---

## 测试分类

### Category 1: 基础交互测试

#### Test 1.1: TUI 启动和关闭
**场景**: 验证 TUI 可以正常启动和退出

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.asyncio
async def test_tui_launch_and_exit():
    """Test TUI can launch and exit cleanly."""
    # Given: Real agent instance
    agent = create_real_agent()

    # When: Launch TUI in test mode
    app = PiCodingAgentApp(agent=agent)

    # Then: App should initialize successfully
    assert app.agent == agent
    assert app._input_handler is not None

    # When: Exit app
    app.exit()

    # Then: Should exit cleanly without errors
```

**预期结果**: TUI 正常启动，显示界面元素（Header, Input, Output, Footer）
**失败场景**:
- App 初始化失败
- 组件加载错误
- 退出时资源未释放

---

#### Test 1.2: 简单文本对话
**场景**: 发送简单消息，验证响应显示

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_simple_conversation():
    """Test basic text conversation in TUI."""
    # Given: TUI app with real agent
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track text deltas
    received_text = []

    def capture_text_delta(event):
        received_text.append(event.get("delta", ""))

    agent.on("text_delta", capture_text_delta)

    # When: Send simple message
    await app._input_handler("Say hi")

    # Wait for response
    await asyncio.sleep(2)

    # Then: Should have received text
    full_response = "".join(received_text)
    assert len(full_response) > 0
    assert any(word in full_response.lower() for word in ["hi", "hello", "greetings"])
```

**预期结果**:
- 用户消息显示在界面
- LLM 响应流式显示（逐字输出）
- 响应完整且合理

**失败场景**:
- 无响应或响应为空
- 文本不流式显示（一次性显示全部）
- UI 不更新

---

### Category 2: 工具执行可视化测试

#### Test 2.1: Bash 工具执行和结果显示
**场景**: 执行 bash 命令，验证工具调用过程和结果在 UI 中正确显示

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_bash_tool_execution():
    """Test bash tool execution is visible in TUI."""
    # Given: TUI app
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track tool events
    tool_events = []

    def capture_tool_start(event):
        tool_events.append({"type": "start", "tool": event.get("tool_name")})

    def capture_tool_end(event):
        tool_events.append({
            "type": "end",
            "tool": event.get("tool_name"),
            "result": event.get("result"),
            "error": event.get("error")
        })

    agent.on("agent_tool_call_start", capture_tool_start)
    agent.on("agent_tool_call_end", capture_tool_end)

    # When: Ask to run a bash command
    await app._input_handler("Run pwd command")
    await asyncio.sleep(3)

    # Then: Should have tool call events
    assert len(tool_events) >= 2  # start + end

    # Check start event
    start_event = next((e for e in tool_events if e["type"] == "start"), None)
    assert start_event is not None
    assert start_event["tool"] == "bash"

    # Check end event
    end_event = next((e for e in tool_events if e["type"] == "end"), None)
    assert end_event is not None
    assert end_event["error"] is None

    result = end_event["result"]
    assert result is not None
    # Check result is a BashResult with stdout
    if isinstance(result, dict):
        assert "stdout" in result
        assert len(result["stdout"]) > 0
```

**预期结果**:
- 显示 "🔧 bash" 或类似工具执行指示器
- 显示命令执行结果（stdout）
- 结果格式化清晰（包含 exit code, stdout, stderr）
- 成功状态显示为绿色/成功样式

**失败场景**:
- 工具执行但 UI 无显示
- 结果格式错误或截断
- 错误信息不清晰

---

#### Test 2.2: Read 工具执行
**场景**: 读取文件内容，验证文件内容在 TUI 中正确展示

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_read_file_tool(test_workspace):
    """Test read file tool execution in TUI."""
    # Given: Test file and TUI
    test_file = test_workspace / "test.txt"
    test_file.write_text("Hello TUI World\nLine 2\nLine 3")

    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track tool results
    tool_results = []

    def capture_tool_end(event):
        tool_results.append(event.get("result"))

    agent.on("agent_tool_call_end", capture_tool_end)

    # When: Ask to read the file
    await app._input_handler(f"Read the file {test_file}")
    await asyncio.sleep(3)

    # Then: Should have result with file content
    assert len(tool_results) > 0
    result = tool_results[0]

    if isinstance(result, dict):
        # Check read result format
        assert "file_path" in result or "content" in result
        content = result.get("content", "")
        assert "Hello TUI World" in content
```

**预期结果**:
- 显示 "📄 Read N lines from <path>"
- 显示文件内容预览（前 200 字符）
- 格式化美观

**失败场景**:
- 文件读取但内容未显示
- 预览截断不当
- 编码问题导致乱码

---

#### Test 2.3: Write 工具执行
**场景**: 创建新文件，验证成功消息

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_write_file_tool(test_workspace):
    """Test write file tool execution in TUI."""
    # Given: TUI and empty workspace
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    new_file = test_workspace / "new_file.py"

    # When: Ask to create file
    await app._input_handler(
        f"Create a file {new_file} with content: print('Hello from TUI')"
    )
    await asyncio.sleep(3)

    # Then: File should be created
    assert new_file.exists()
    content = new_file.read_text()
    assert "Hello from TUI" in content
```

**预期结果**:
- 显示 "✍️ Wrote file: <path>"
- 文件实际被创建
- 成功样式（绿色）

---

#### Test 2.4: Edit 工具执行
**场景**: 编辑现有文件

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_edit_file_tool(test_workspace):
    """Test edit file tool execution in TUI."""
    # Given: Existing file
    test_file = test_workspace / "edit_test.py"
    test_file.write_text("old_value = 123")

    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # When: Ask to edit
    await app._input_handler(
        f"In {test_file}, change 'old_value' to 'new_value'"
    )
    await asyncio.sleep(3)

    # Then: File should be modified
    content = test_file.read_text()
    assert "new_value" in content
    assert "old_value" not in content
```

**预期结果**:
- 显示 "✏️ Made N replacement(s) in <path>"
- 实际修改成功

---

#### Test 2.5: Grep 工具执行
**场景**: 搜索文件内容

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_grep_search_tool(test_workspace):
    """Test grep search tool execution in TUI."""
    # Given: Files with searchable content
    (test_workspace / "file1.py").write_text("def hello():\n    pass")
    (test_workspace / "file2.py").write_text("def world():\n    pass")
    (test_workspace / "file3.py").write_text("def hello_world():\n    pass")

    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # When: Search for pattern
    await app._input_handler(f"Search for 'hello' in Python files in {test_workspace}")
    await asyncio.sleep(3)

    # Then: Should find matches
    # (验证通过检查 tool_results)
```

**预期结果**:
- 显示 "🔍 Found N match(es)"
- 列出前几个匹配（文件名:行号）
- 截断提示（如果结果太多）

---

### Category 3: 多轮对话测试

#### Test 3.1: 上下文保持
**场景**: 多轮对话，验证上下文保持

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_multi_turn_context(test_workspace):
    """Test context preservation across multiple turns in TUI."""
    # Given: TUI and test file
    test_file = test_workspace / "number.txt"
    test_file.write_text("42")

    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Turn 1: Read file
    await app._input_handler(f"What's in {test_file}?")
    await asyncio.sleep(2)

    # Then: Agent should know it's 42
    assert len(agent.context.messages) >= 2

    # Turn 2: Reference previous content
    await app._input_handler("Double that number")
    await asyncio.sleep(2)

    # Then: Should calculate 84 based on context
    # (检查最终响应中包含 84)
```

**预期结果**:
- 第二轮对话能引用第一轮的信息
- 消息历史正确保存
- UI 显示完整对话历史

---

### Category 4: 错误处理测试

#### Test 4.1: 工具执行错误
**场景**: 工具执行失败时的错误显示

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_tool_execution_error():
    """Test tool execution error is displayed correctly in TUI."""
    # Given: TUI
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track errors
    errors = []

    def capture_error(event):
        errors.append(event.get("error"))

    agent.on("agent_tool_call_end", lambda e: e.get("error") and capture_error(e))

    # When: Try to read non-existent file
    await app._input_handler("Read the file /nonexistent/path/file.txt")
    await asyncio.sleep(3)

    # Then: Should show error
    assert len(errors) > 0
    # Error should be displayed in red/error style
```

**预期结果**:
- 错误消息清晰显示（红色文字）
- 包含错误原因
- 不崩溃或卡死

---

#### Test 4.2: API 错误恢复
**场景**: API 调用失败后的恢复

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_api_error_recovery():
    """Test TUI can recover from API errors."""
    # Given: TUI
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track system messages
    system_messages = []

    def capture_system_msg(role, content):
        if role == "system":
            system_messages.append(content)

    # Patch append_message to capture
    original_append = app.append_message
    app.append_message = lambda r, c: (capture_system_msg(r, c), original_append(r, c))

    # When: Simulate error scenario (or force one)
    # ... trigger error

    # Then: Error should be displayed but app continues
    # User can still send new messages
```

**预期结果**:
- 错误显示但不退出
- 可以继续发送新消息
- 上下文状态一致

---

### Category 5: UI 组件测试

#### Test 5.1: 流式文本显示
**场景**: 验证文本流式显示效果

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_streaming_text_display():
    """Test text is displayed in streaming fashion."""
    # Given: TUI
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # Track deltas
    deltas = []

    def capture_delta(event):
        delta = event.get("delta", "")
        if delta:
            deltas.append(delta)

    agent.on("text_delta", capture_delta)

    # When: Send message
    await app._input_handler("Write a short story")
    await asyncio.sleep(3)

    # Then: Should have multiple deltas (streaming)
    assert len(deltas) > 5  # Should be broken into chunks
```

**预期结果**:
- 文本逐步显示（不是一次性）
- 显示流畅，无闪烁
- 自动滚动到底部

---

#### Test 5.2: Markdown 渲染
**场景**: 验证 Markdown 内容正确渲染

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_tui_markdown_rendering():
    """Test markdown content is rendered correctly."""
    # Given: TUI
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # When: Request formatted response
    await app._input_handler("Show me a code example in markdown")
    await asyncio.sleep(3)

    # Then: Markdown should be rendered
    # (检查 Rich Markdown 渲染)
```

**预期结果**:
- 代码块有语法高亮
- 标题、列表格式正确
- 链接可识别

---

### Category 6: 性能和稳定性测试

#### Test 6.1: 长对话性能
**场景**: 多次对话后性能不下降

```python
@pytest.mark.e2e
@pytest.mark.tui
@pytest.mark.requires_api
@pytest.mark.slow
@pytest.mark.asyncio
async def test_tui_long_conversation_performance():
    """Test TUI performance with long conversation history."""
    # Given: TUI
    agent = create_real_agent()
    app = PiCodingAgentApp(agent=agent)

    # When: Send 10 messages
    for i in range(10):
        await app._input_handler(f"Message {i}")
        await asyncio.sleep(1)

    # Then: UI should still be responsive
    assert len(agent.context.messages) == 20  # 10 user + 10 assistant
```

**预期结果**:
- 响应时间稳定
- 内存使用合理
- UI 不卡顿

---

## 测试运行策略

### 快速测试（不需要 API）
```bash
pytest tests/test_tui_e2e.py -m "e2e and tui and not requires_api" -v
```

### 完整测试（需要 API）
```bash
export OPENAI_API_KEY=your-key
pytest tests/test_tui_e2e.py -m "e2e and tui" -v
```

### 只测试工具执行
```bash
pytest tests/test_tui_e2e.py -k "tool" -v
```

### 慢速测试
```bash
pytest tests/test_tui_e2e.py -m "slow" -v
```

---

## 测试优先级

### P0 (最高优先级) - 核心功能
- ✅ Test 1.2: 简单文本对话
- ✅ Test 2.1: Bash 工具执行
- ✅ Test 2.2: Read 工具执行
- ✅ Test 4.1: 工具执行错误处理

### P1 (高优先级) - 主要工具
- ✅ Test 2.3: Write 工具执行
- ✅ Test 2.4: Edit 工具执行
- ✅ Test 2.5: Grep 工具执行
- ✅ Test 3.1: 多轮对话上下文

### P2 (中优先级) - UI 和体验
- ⚠️ Test 5.1: 流式文本显示
- ⚠️ Test 5.2: Markdown 渲染
- ⚠️ Test 1.1: 启动和关闭

### P3 (低优先级) - 稳定性
- ⚠️ Test 6.1: 长对话性能
- ⚠️ Test 4.2: API 错误恢复

---

## 实现注意事项

### 1. Textual 测试限制
- Textual App 需要终端环境，单元测试中难以完全模拟
- 可以测试事件处理逻辑，但完整 UI 渲染需要特殊设置
- 建议使用 Textual 的 `pilot` 模式进行 UI 交互测试

### 2. 同线程 UI 更新（重要）
- Agent 与 TUI 运行在同一 asyncio 事件循环，事件回调在 app 线程执行
- 必须在回调中**直接调用** app 方法（如 `app.append_text`），**不能**使用 `call_from_thread()`，否则会报错："The call_from_thread method must run in a different thread from the app"
- **该场景由单元测试覆盖**：`test_tui_mode.py::test_tui_handlers_update_ui_directly_no_call_from_thread`，E2E 用例未启动完整 TUI，不覆盖此路径

### 3. 异步事件处理
- 当前 E2E 用例只直接调用 `real_agent.run()`，不启动 TUI 界面，因此只验证 agent 事件与工具结果
- 测试时可直接监听 agent 事件；若将来用 Textual pilot 跑完整 TUI，需适当 `await` 等待 UI 更新

### 4. 工具结果格式化
- `_format_tool_result()` 函数将工具结果转换为友好显示
- 测试时需要验证格式化逻辑正确
- 确保所有工具类型都有格式化处理

### 5. Mock vs 真实 API
- 基础测试可以 mock agent 事件
- 完整 E2E 测试需要真实 API 调用
- 使用 `@pytest.mark.requires_api` 标记真实 API 测试

---

## 测试工具和辅助函数

### 创建测试 Agent
```python
def create_real_agent():
    """Create a real agent instance for TUI testing."""
    from basket_assistant.agent import AssistantAgent
    return AssistantAgent(load_extensions=False).agent
```

### 捕获 TUI 输出
```python
def capture_tui_output(app):
    """Capture output from TUI app for verification."""
    output_widget = app.query_one("#output")
    return output_widget.lines
```

### 模拟用户输入
```python
async def simulate_user_input(app, text):
    """Simulate user typing and submitting input."""
    input_widget = app.query_one("#input")
    input_widget.value = text
    await input_widget.action_submit()
```

---

## 成功标准

E2E 测试通过的标准：

1. **核心对话流程** (P0)
   - 简单对话能正常往返
   - 工具能被触发和执行
   - 结果正确显示

2. **所有工具可用** (P0-P1)
   - bash, read, write, edit, grep 都能执行
   - 结果格式化美观
   - 错误处理正确

3. **多轮对话稳定** (P1)
   - 上下文正确保持
   - 长对话不崩溃

4. **用户体验良好** (P2)
   - 流式显示流畅
   - UI 响应及时
   - 错误提示清晰

---

## 下一步

1. 实现 P0 优先级测试
2. 验证所有工具在 TUI 中可用
3. 修复发现的 bug
4. 扩展到 P1 和 P2 测试
5. 集成到 CI/CD 流程

