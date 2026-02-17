# Pi-Coding-Agent Test Suite

This directory contains the test suite for pi-coding-agent. The tests ensure the agent's core functionality, tools, and integrations work correctly.

## Test Organization

### Unit Tests
Tests for individual components in isolation:
- `test_bash_tool.py` - Bash command execution
- `test_read_tool.py` - File reading with line ranges
- `test_write_tool.py` - File writing and creation
- `test_edit_tool.py` - String replacement editing
- `test_grep_tool.py` - Pattern searching
- `test_settings.py` - Settings management
- `test_session_manager.py` - JSONL session persistence
- `test_messages.py` - Message tree navigation
- `test_theme.py` - Theme system
- `test_extensions.py` - Extension loading and API

### Integration Tests
Tests for component interactions:
- `test_coding_agent_integration.py` - CodingAgent class integration with pi-agent and pi-ai

### End-to-End Tests
Tests for complete user workflows:
- `test_e2e_workflows.py` - Full agent workflows (planned)
- `test_main.py` - CLI entry point tests (planned)
- `test_tui_mode.py` - TUI mode integration (minimal)

## Running Tests

### Run All Tests
```bash
cd packages/pi-coding-agent
poetry run pytest -v
```

### Run Specific Test Categories
```bash
# Unit tests only
poetry run pytest -m unit -v

# Integration tests only
poetry run pytest -m integration -v

# End-to-end tests only
poetry run pytest -m e2e -v

# Skip slow tests
poetry run pytest -m "not slow" -v
```

### Run Specific Test Files
```bash
# Test a single file
poetry run pytest tests/test_bash_tool.py -v

# Test multiple files
poetry run pytest tests/test_bash_tool.py tests/test_read_tool.py -v
```

### Run Specific Test Functions
```bash
# Test a single function
poetry run pytest tests/test_bash_tool.py::test_bash_simple_command -v

# Test all functions in a class
poetry run pytest tests/test_coding_agent_integration.py::TestCodingAgentIntegration -v
```

### Run with Coverage
```bash
# Generate coverage report
poetry run pytest --cov=pi_coding_agent --cov-report=html tests/

# View coverage report
open htmlcov/index.html
```

### Run in Verbose Mode
```bash
# Show test names and results
poetry run pytest -v

# Show full output (including print statements)
poetry run pytest -v -s

# Show local variables on failure
poetry run pytest -v -l
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for component interaction
- `@pytest.mark.e2e` - End-to-end tests for complete workflows
- `@pytest.mark.slow` - Tests that take a long time to run (e.g., timeouts)
- `@pytest.mark.asyncio` - Async tests (most tests use this)

## Test Fixtures

Shared fixtures are defined in `conftest.py`:

### Directory Fixtures
- `temp_project_dir` - Temporary directory with sample files (test.txt, example.py, README.md, subdir/nested.txt)
- `tmp_path` - pytest built-in temporary directory

### Settings Fixtures
- `mock_settings_manager` - SettingsManager with temporary settings directory

### Agent Fixtures
- `mock_coding_agent` - Fully initialized CodingAgent with mocked LLM (no API calls)
- `mock_agent` - Mock Agent instance
- `mock_model` - Mock Model object
- `sample_context` - Sample Context with a few messages

### Response Fixtures
- `mock_text_response` - Mock LLM response with just text
- `mock_tool_call_response` - Mock LLM response with tool call

## Coverage Goals

Current test coverage (as of Phase 1):

| Component | Coverage | Status |
|-----------|----------|--------|
| **Tools** | ~95% | ✅ Excellent |
| `bash.py` | ~95% | ✅ Excellent |
| `read.py` | ~95% | ✅ Excellent |
| `write.py` | ~95% | ✅ Excellent |
| `edit.py` | ~95% | ✅ Excellent |
| `grep.py` | ~95% | ✅ Excellent |
| **Core** | ~80% | ✅ Good |
| `settings.py` | ~90% | ✅ Excellent |
| `session_manager.py` | ~85% | ✅ Good |
| `messages.py` | ~90% | ✅ Excellent |
| `theme.py` | ~75% | ✅ Good |
| **Integration** | ~40% | ⚠️ Needs Work |
| `main.py` | ~30% | ⚠️ Needs Work |
| `modes/tui.py` | ~25% | ⚠️ Needs Work |
| **Extensions** | ~85% | ✅ Good |
| `extensions/api.py` | ~90% | ✅ Excellent |
| `extensions/loader.py` | ~80% | ✅ Good |

**Target Coverage: >80% for all components**

## Writing New Tests

### Test Structure
```python
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
async def test_my_feature(temp_project_dir):
    """Test description."""
    # Arrange
    input_data = ...

    # Act
    result = await my_function(input_data)

    # Assert
    assert result == expected_value
```

### Best Practices
1. **Use descriptive test names** - `test_bash_command_with_exit_code` not `test_1`
2. **One assertion per test** - Keep tests focused and specific
3. **Use fixtures** - Reuse setup code from conftest.py
4. **Mock external dependencies** - Don't make actual API calls
5. **Test both success and failure** - Include error cases
6. **Use markers** - Tag tests with appropriate markers
7. **Add docstrings** - Explain what the test validates

### Testing Async Functions
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Testing Exceptions
```python
def test_function_raises_exception():
    with pytest.raises(ValueError):
        function_that_should_raise()
```

### Using Mocks
```python
from unittest.mock import AsyncMock, MagicMock

def test_with_mock(monkeypatch):
    mock_func = MagicMock(return_value="mocked")
    monkeypatch.setattr("module.function", mock_func)

    result = function_that_uses_mock()
    assert result == "mocked"
    mock_func.assert_called_once()
```

## CI/CD Integration

### GitHub Actions (Planned)
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      - name: Run tests
        run: poetry run pytest -v --cov=pi_coding_agent
```

### Pre-commit Hook (Optional)
```bash
# .git/hooks/pre-commit
#!/bin/bash
poetry run pytest -m "not slow"
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Debugging Tests

### Run with pdb
```bash
# Drop into debugger on failure
poetry run pytest --pdb

# Drop into debugger at start of test
poetry run pytest --trace
```

### Show print statements
```bash
# Show all output
poetry run pytest -s

# Show output only on failure
poetry run pytest --capture=no
```

### Show detailed failure info
```bash
# Show local variables
poetry run pytest -l

# Show full diff on assertion failure
poetry run pytest -vv

# Show detailed traceback
poetry run pytest --tb=long
```

## Known Issues

### Integration Test Fixture Issues
The `mock_coding_agent` fixture needs adjustment to properly mock the model. Some integration tests may fail due to:
- Incorrect monkeypatching of `get_model`
- SettingsManager `.settings` attribute access

**Workaround:** Update tests to use `from pi_ai import api` and patch `api.get_model`.

### Async Test Warnings
Some tests may show warnings about unclosed async generators. These are typically harmless but should be addressed for cleaner test output.

## Contributing Tests

When adding new features:

1. **Write tests first** (TDD approach)
2. **Ensure all tests pass** before submitting PR
3. **Add tests for bug fixes** to prevent regression
4. **Maintain coverage** - aim for >80% on new code
5. **Update this README** if adding new test patterns

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Python testing best practices](https://realpython.com/pytest-python-testing/)

## Contact

For questions about tests, see the main project README or open an issue.
