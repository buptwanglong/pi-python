# End-to-End Test Scenarios for Pi-Coding-Agent

## Overview

端到端测试（E2E Tests）验证完整的用户工作流，使用真实的组件（而非 Mock）。
这些测试能发现集成测试和单元测试无法发现的问题，如 API 兼容性、网络问题、真实数据流等。

---

## Test Strategy

### E2E 测试的特点
- ✅ 使用真实的 LLM API（需要 API key）
- ✅ 使用真实的文件系统操作
- ✅ 使用真实的 shell 命令
- ✅ 测试完整的用户场景
- ⚠️ 较慢（需要网络调用）
- ⚠️ 可能不稳定（依赖外部服务）

### 测试分类
1. **Happy Path Tests** - 正常流程测试
2. **Error Path Tests** - 错误场景测试
3. **Tool Integration Tests** - 工具集成测试
4. **Multi-Turn Tests** - 多轮对话测试
5. **API Compatibility Tests** - API 兼容性测试

---

## Category 1: Happy Path Tests (正常流程)

### Test 1.1: Basic Text-Only Conversation
**场景**: 不使用工具的简单对话
```python
async def test_e2e_simple_conversation():
    """用户发送简单消息，agent 用文本回复（不调用工具）"""
    # Given: 一个新的 agent
    agent = AssistantAgent(load_extensions=False)

    # When: 发送不需要工具的消息
    response = await agent.run_once("Say hello in one word")

    # Then: 应该收到文本响应
    assert response
    assert len(response) > 0
    assert "hello" in response.lower() or "hi" in response.lower()
```

**预期结果**: Agent 返回简单的文本响应
**失败场景**: API 调用失败、网络问题、认证失败

---

### Test 1.2: Read File Workflow
**场景**: 用户要求读取文件，agent 使用 read 工具
```python
async def test_e2e_read_file_workflow(temp_project_dir):
    """完整的读取文件流程"""
    # Given: 一个包含测试文件的目录
    test_file = temp_project_dir / "test.txt"
    test_file.write_text("Hello World\nThis is a test file")

    agent = AssistantAgent(load_extensions=False)

    # When: 要求读取文件
    response = await agent.run_once(f"Read the file {test_file}")

    # Then: 应该包含文件内容
    assert "Hello World" in response
    assert "test file" in response
```

**预期结果**: Agent 调用 read 工具并返回文件内容
**失败场景**:
- Agent 不调用工具
- 工具调用失败
- API 不支持 tools 参数 ⚠️（就是现在的问题）

---

### Test 1.3: Write File Workflow
**场景**: 用户要求创建文件，agent 使用 write 工具
```python
async def test_e2e_write_file_workflow(tmp_path):
    """完整的创建文件流程"""
    # Given: 临时目录
    os.chdir(tmp_path)
    agent = AssistantAgent(load_extensions=False)

    # When: 要求创建文件
    response = await agent.run_once(
        "Create a file called hello.py with a function that prints 'Hello World'"
    )

    # Then: 文件应该被创建
    hello_file = tmp_path / "hello.py"
    assert hello_file.exists()
    content = hello_file.read_text()
    assert "def" in content
    assert "Hello World" in content
```

**预期结果**: Agent 创建文件，内容符合要求
**失败场景**:
- 文件未创建
- 内容不正确
- 权限问题

---

### Test 1.4: Edit File Workflow
**场景**: 用户要求修改现有文件，agent 使用 edit 工具
```python
async def test_e2e_edit_file_workflow(temp_project_dir):
    """完整的编辑文件流程"""
    # Given: 一个现有文件
    test_file = temp_project_dir / "code.py"
    test_file.write_text("def hello():\n    print('Hi')\n")

    agent = AssistantAgent(load_extensions=False)

    # When: 要求修改文件
    response = await agent.run_once(
        f"In {test_file}, change 'Hi' to 'Hello World'"
    )

    # Then: 文件应该被修改
    content = test_file.read_text()
    assert "Hello World" in content
    assert "Hi" not in content or "Hi" in "Hello World"
```

**预期结果**: Agent 正确修改文件
**失败场景**:
- 匹配字符串失败
- 修改错误的内容
- 文件损坏

---

### Test 1.5: Bash Command Workflow
**场景**: 用户要求执行命令，agent 使用 bash 工具
```python
async def test_e2e_bash_command_workflow():
    """完整的命令执行流程"""
    # Given: 新的 agent
    agent = AssistantAgent(load_extensions=False)

    # When: 要求执行命令
    response = await agent.run_once("Run the command 'echo Hello World'")

    # Then: 应该看到命令输出
    assert "Hello World" in response
```

**预期结果**: Agent 执行命令并返回输出
**失败场景**:
- 命令执行失败
- 超时
- 权限问题

---

### Test 1.6: Grep Search Workflow
**场景**: 用户要求搜索内容，agent 使用 grep 工具
```python
async def test_e2e_grep_search_workflow(temp_project_dir):
    """完整的搜索流程"""
    # Given: 包含多个文件的目录
    (temp_project_dir / "file1.py").write_text("def hello():\n    pass")
    (temp_project_dir / "file2.py").write_text("def world():\n    pass")
    (temp_project_dir / "file3.txt").write_text("hello world")

    agent = AssistantAgent(load_extensions=False)

    # When: 要求搜索
    response = await agent.run_once(
        f"Search for 'hello' in Python files in {temp_project_dir}"
    )

    # Then: 应该找到匹配项
    assert "file1.py" in response
    assert "hello" in response.lower()
```

**预期结果**: Agent 搜索并返回匹配结果
**失败场景**:
- 搜索失败
- 结果不准确
- 性能问题

---

## Category 2: Multi-Turn Tests (多轮对话)

### Test 2.1: Context Preservation Across Turns
**场景**: 多轮对话中保持上下文
```python
async def test_e2e_multi_turn_context(temp_project_dir):
    """测试多轮对话的上下文保持"""
    # Given: 新的 agent
    agent = AssistantAgent(load_extensions=False)
    test_file = temp_project_dir / "data.txt"
    test_file.write_text("42")

    # When: 第一轮 - 读取文件
    response1 = await agent.run_once(f"What's in {test_file}?")
    assert "42" in response1

    # When: 第二轮 - 引用之前的内容
    response2 = await agent.run_once("Double that number")

    # Then: 应该记得之前的内容
    assert "84" in response2
```

**预期结果**: Agent 在多轮对话中保持上下文
**失败场景**:
- 上下文丢失
- 信息混淆
- 响应不连贯

---

### Test 2.2: Multi-Step Task with Multiple Tools
**场景**: 需要使用多个工具的复杂任务
```python
async def test_e2e_multi_tool_workflow(temp_project_dir):
    """测试需要多个工具的任务"""
    # Given: 目录和 agent
    agent = AssistantAgent(load_extensions=False)

    # When: 复杂任务：创建、修改、验证
    response = await agent.run_once(
        f"Create a file hello.py with a hello function, "
        f"then add a goodbye function to it, "
        f"then show me the final content"
    )

    # Then: 文件应该包含两个函数
    hello_file = temp_project_dir / "hello.py"
    if hello_file.exists():
        content = hello_file.read_text()
        assert "hello" in content.lower()
        assert "goodbye" in content.lower()
```

**预期结果**: Agent 按顺序完成多步任务
**失败场景**:
- 步骤顺序错误
- 中间步骤失败
- 结果不完整

---

## Category 3: Error Handling Tests (错误处理)

### Test 3.1: Handle File Not Found
**场景**: 请求读取不存在的文件
```python
async def test_e2e_file_not_found_error():
    """测试文件不存在的错误处理"""
    # Given: agent
    agent = AssistantAgent(load_extensions=False)

    # When: 尝试读取不存在的文件
    response = await agent.run_once("Read /nonexistent/file.txt")

    # Then: 应该优雅地处理错误
    assert "not found" in response.lower() or "does not exist" in response.lower()
    # 不应该崩溃
```

**预期结果**: Agent 报告错误但不崩溃
**失败场景**:
- Agent 崩溃
- 无错误提示
- 错误信息不清楚

---

### Test 3.2: Handle Command Timeout
**场景**: 执行超时的命令
```python
async def test_e2e_command_timeout():
    """测试命令超时处理"""
    # Given: agent
    agent = AssistantAgent(load_extensions=False)

    # When: 执行会超时的命令
    response = await agent.run_once("Run the command 'sleep 300'")

    # Then: 应该报告超时
    assert "timeout" in response.lower() or "timed out" in response.lower()
```

**预期结果**: Agent 检测超时并报告
**失败场景**:
- Agent 挂起
- 无超时处理
- 用户体验差

---

### Test 3.3: Handle Invalid Edit Pattern
**场景**: 编辑时使用不存在的匹配字符串
```python
async def test_e2e_edit_pattern_not_found(temp_project_dir):
    """测试编辑失败的处理"""
    # Given: 文件和 agent
    test_file = temp_project_dir / "test.py"
    test_file.write_text("def hello():\n    pass")

    agent = AssistantAgent(load_extensions=False)

    # When: 尝试替换不存在的内容
    response = await agent.run_once(
        f"In {test_file}, change 'nonexistent' to 'something'"
    )

    # Then: 应该报告找不到
    assert "not found" in response.lower() or "cannot find" in response.lower()
```

**预期结果**: Agent 报告匹配失败
**失败场景**:
- 错误修改文件
- 无错误提示
- 数据损坏

---

### Test 3.4: Recover from API Error
**场景**: API 调用失败后恢复
```python
async def test_e2e_api_error_recovery():
    """测试 API 错误恢复"""
    # Given: agent with error recovery
    agent = AssistantAgent(load_extensions=False)

    # Simulate first call fails, second succeeds
    # (This needs special setup or real intermittent API)

    # When: 发送消息
    try:
        response = await agent.run_once("Say hi")
    except Exception as e:
        # Then: 上下文应该恢复
        assert len(agent.context.messages) == 1  # Only user message
```

**预期结果**: 错误后上下文保持一致
**失败场景**:
- 上下文损坏
- 消息丢失
- 状态不一致

---

## Category 4: API Compatibility Tests (API 兼容性)

### Test 4.1: API Supports Tools Parameter
**场景**: 验证 API 是否支持 tools 参数（就是现在的问题！）
```python
async def test_e2e_api_supports_tools():
    """测试 API 是否支持工具调用"""
    # Given: agent with tools
    agent = AssistantAgent(load_extensions=False)

    # When: 发送需要工具的消息
    response = await agent.run_once("What files are in current directory?")

    # Then: 不应该有 tools 参数错误
    assert "unexpected keyword argument 'tools'" not in str(response).lower()
    assert len(response) > 0
```

**预期结果**: API 接受 tools 参数
**失败场景**:
- API 不支持 tools ⚠️ **当前问题**
- 工具调用被忽略
- 返回错误

---

### Test 4.2: API Returns Valid Response Format
**场景**: 验证 API 响应格式
```python
async def test_e2e_api_response_format():
    """测试 API 响应格式是否正确"""
    # Given: agent
    agent = AssistantAgent(load_extensions=False)

    # When: 发送消息
    response = await agent.run_once("Say hi")

    # Then: 响应应该是字符串
    assert isinstance(response, str)
    assert len(response) > 0
    # 不应该是错误对象
    assert not response.startswith("Error:")
```

**预期结果**: API 返回预期格式
**失败场景**:
- 格式不匹配
- 解析失败
- 数据丢失

---

### Test 4.3: API Handles Streaming
**场景**: 验证流式响应
```python
async def test_e2e_api_streaming():
    """测试 API 流式响应"""
    # Given: agent with streaming enabled
    agent = AssistantAgent(load_extensions=False)

    # Capture streamed text
    streamed_chunks = []
    original_handler = None

    for handler, _ in agent.agent._event_handlers.get("text_delta", []):
        original_handler = handler
        def capture_handler(event):
            streamed_chunks.append(event.get("delta", ""))
            original_handler(event)
        break

    # When: 发送消息
    await agent.run_once("Count from 1 to 5")

    # Then: 应该有多个 chunk
    assert len(streamed_chunks) > 1
```

**预期结果**: 响应是流式传输的
**失败场景**:
- 不支持流式
- 流式中断
- 数据不完整

---

## Category 5: Performance Tests (性能测试)

### Test 5.1: Response Time
**场景**: 验证响应时间在合理范围内
```python
async def test_e2e_response_time():
    """测试响应时间"""
    # Given: agent
    agent = AssistantAgent(load_extensions=False)

    # When: 发送简单消息
    import time
    start = time.time()
    response = await agent.run_once("Say hi in one word")
    elapsed = time.time() - start

    # Then: 应该在合理时间内响应（如 10 秒）
    assert elapsed < 10.0
    assert response
```

**预期结果**: 响应快速
**失败场景**:
- 超时
- 网络延迟
- API 限流

---

### Test 5.2: Large File Handling
**场景**: 处理大文件
```python
async def test_e2e_large_file_handling(temp_project_dir):
    """测试处理大文件"""
    # Given: 大文件（1000行）
    large_file = temp_project_dir / "large.txt"
    large_file.write_text("line\n" * 1000)

    agent = AssistantAgent(load_extensions=False)

    # When: 读取大文件
    response = await agent.run_once(f"How many lines in {large_file}?")

    # Then: 应该能处理
    assert "1000" in response
```

**预期结果**: 能处理大文件
**失败场景**:
- 内存溢出
- 超时
- 响应不完整

---

## Category 6: Settings and Configuration Tests (配置测试)

### Test 6.1: Custom Settings
**场景**: 使用自定义配置
```python
async def test_e2e_custom_settings(tmp_path):
    """测试自定义配置"""
    # Given: 自定义 settings
    from basket_assistant.core import SettingsManager
    settings_manager = SettingsManager(tmp_path / "settings.json")
    settings = settings_manager.load()
    settings.agent.max_turns = 3
    settings_manager.save(settings)

    agent = AssistantAgent(settings_manager=settings_manager, load_extensions=False)

    # When: 运行 agent
    # Then: 应该使用自定义配置
    assert agent.agent.max_turns == 3
```

**预期结果**: 自定义配置生效
**失败场景**:
- 配置被忽略
- 使用默认值
- 配置损坏

---

### Test 6.2: Different Model Providers
**场景**: 测试不同的模型提供商
```python
@pytest.mark.parametrize("provider,model_id", [
    ("anthropic", "claude-sonnet-4-20250514"),
    ("openai", "gpt-4o-mini"),
])
async def test_e2e_different_providers(provider, model_id):
    """测试不同的模型提供商"""
    # Skip if no API key
    if not os.getenv(f"{provider.upper()}_API_KEY"):
        pytest.skip(f"No {provider} API key")

    # Given: 配置特定 provider
    settings_manager = SettingsManager()
    settings = settings_manager.load()
    settings.model.provider = provider
    settings.model.model_id = model_id

    agent = AssistantAgent(settings_manager=settings_manager, load_extensions=False)

    # When: 发送消息
    response = await agent.run_once("Say hi")

    # Then: 应该正常工作
    assert response
    assert len(response) > 0
```

**预期结果**: 所有支持的 provider 都能工作
**失败场景**:
- Provider 不支持
- 认证失败
- 格式不兼容

---

## Test Execution Strategy

### 运行策略
```bash
# 1. 快速测试（跳过需要 API 的）
pytest tests/test_e2e_workflows.py -m "not requires_api"

# 2. 完整测试（需要 API key）
pytest tests/test_e2e_workflows.py

# 3. 只测试特定类别
pytest tests/test_e2e_workflows.py -k "happy_path"
pytest tests/test_e2e_workflows.py -k "error_handling"
pytest tests/test_e2e_workflows.py -k "api_compatibility"

# 4. 慢速测试
pytest tests/test_e2e_workflows.py -m slow
```

### 测试标记
```python
@pytest.mark.e2e              # 所有 E2E 测试
@pytest.mark.requires_api     # 需要真实 API key
@pytest.mark.slow             # 慢速测试（>5秒）
@pytest.mark.network          # 需要网络
@pytest.mark.filesystem       # 需要文件系统访问
```

---

## Summary

### 测试场景总计: 20+ 个

| 类别 | 测试数 | 优先级 |
|------|--------|--------|
| Happy Path | 6 | 🔴 高 |
| Multi-Turn | 2 | 🟡 中 |
| Error Handling | 4 | 🔴 高 |
| API Compatibility | 3 | 🔴 高（当前问题！） |
| Performance | 2 | 🟢 低 |
| Configuration | 2 | 🟡 中 |

### 关键测试（能发现当前问题）
- ✅ **Test 4.1: API Supports Tools Parameter** - 会立即发现当前的 tools 参数问题
- ✅ **Test 1.2-1.6: Tool Workflows** - 验证工具调用是否工作
- ✅ **Test 3.4: API Error Recovery** - 验证错误恢复机制

这些测试如果存在，**就能在用户使用前发现问题**！
