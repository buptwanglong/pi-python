# /create-skill Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/create-skill` command that creates reusable skills from conversation content, with AI-generated drafts and user confirmation.

**Architecture:** Register an async command handler in `handlers.py` that reads session history, calls `complete()` to generate a SKILL.md draft, previews it, lets user confirm/edit, then writes to the chosen scope directory and refreshes the skill index.

**Tech Stack:** Python 3.12+, Pydantic v2, basket-ai `complete()`, aiofiles, pytest + tmp_path

---

### Task 1: Create SkillDraft model and name sanitizer

**Files:**
- Create: `packages/basket-assistant/basket_assistant/commands/__init__.py`
- Create: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Create the commands package init**

```python
# packages/basket-assistant/basket_assistant/commands/__init__.py
"""Command implementations for basket-assistant."""
```

**Step 2: Write the failing test for SkillDraft and sanitize_skill_name**

```python
# packages/basket-assistant/tests/test_create_skill.py
"""Tests for /create-skill command."""

import pytest
from pydantic import ValidationError

from basket_assistant.commands.create_skill import SkillDraft, sanitize_skill_name


class TestSkillDraft:
    """Tests for SkillDraft Pydantic model."""

    def test_valid_draft(self):
        draft = SkillDraft(
            name="my-skill",
            description="A useful skill",
            body="# My Skill\n\nDo things.",
        )
        assert draft.name == "my-skill"
        assert draft.description == "A useful skill"
        assert draft.body == "# My Skill\n\nDo things."

    def test_name_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            SkillDraft(name="", description="desc", body="body")

    def test_name_must_match_pattern(self):
        with pytest.raises(ValidationError):
            SkillDraft(name="Invalid Name!", description="desc", body="body")

    def test_description_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            SkillDraft(name="ok", description="", body="body")


class TestSanitizeSkillName:
    """Tests for sanitize_skill_name."""

    def test_lowercase(self):
        assert sanitize_skill_name("My Skill") == "my-skill"

    def test_replace_special_chars(self):
        assert sanitize_skill_name("hello_world!") == "hello-world"

    def test_collapse_hyphens(self):
        assert sanitize_skill_name("a--b---c") == "a-b-c"

    def test_strip_leading_trailing_hyphens(self):
        assert sanitize_skill_name("-hello-") == "hello"

    def test_truncate_to_64(self):
        long_name = "a" * 100
        result = sanitize_skill_name(long_name)
        assert len(result) <= 64

    def test_already_valid(self):
        assert sanitize_skill_name("valid-name") == "valid-name"

    def test_unicode_stripped(self):
        result = sanitize_skill_name("技能名称test")
        assert result == "test"
```

**Step 3: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'basket_assistant.commands'`

**Step 4: Write minimal implementation**

```python
# packages/basket-assistant/basket_assistant/commands/create_skill.py
"""
/create-skill command: create a reusable skill from conversation content.
"""

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Same constants as skills_loader
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_NAME_MAX_LEN = 64


class SkillScope(str, Enum):
    """Where to save the created skill."""

    PROJECT = "project"
    GLOBAL = "global"


class SkillDraft(BaseModel):
    """Generated skill draft, validated before saving."""

    name: str = Field(..., min_length=1, max_length=_NAME_MAX_LEN)
    description: str = Field(..., min_length=1, max_length=1024)
    body: str = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def name_must_match_pattern(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(
                f"Skill name must match ^[a-z0-9]+(-[a-z0-9]+)*$, got {v!r}"
            )
        return v


def sanitize_skill_name(raw: str) -> str:
    """
    Sanitize a raw string into a valid skill name.

    Rules:
    - Lowercase
    - Replace non-alphanumeric chars with hyphens
    - Collapse consecutive hyphens
    - Strip leading/trailing hyphens
    - Truncate to 64 chars
    """
    # Lowercase and strip
    result = raw.lower().strip()
    # Replace non-alphanumeric (keeping hyphens) with hyphen
    result = re.sub(r"[^a-z0-9-]", "-", result)
    # Collapse consecutive hyphens
    result = re.sub(r"-{2,}", "-", result)
    # Strip leading/trailing hyphens
    result = result.strip("-")
    # Truncate
    if len(result) > _NAME_MAX_LEN:
        result = result[:_NAME_MAX_LEN].rstrip("-")
    return result
```

**Step 5: Run test to verify it passes**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py -v`
Expected: All 9 tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/__init__.py packages/basket-assistant/basket_assistant/commands/create_skill.py packages/basket-assistant/tests/test_create_skill.py
git commit -m "feat: add SkillDraft model and name sanitizer for /create-skill"
```

---

### Task 2: Implement conversation extraction and SKILL.md generation

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Write failing tests for extract_conversation_text and generate_skill_md**

Append to `packages/basket-assistant/tests/test_create_skill.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
from basket_ai.types import (
    AssistantMessage,
    Context,
    TextContent,
    UserMessage,
)
from basket_assistant.commands.create_skill import (
    extract_conversation_text,
    generate_skill_draft,
    format_skill_md,
)


class TestExtractConversationText:
    """Tests for extract_conversation_text."""

    def test_extracts_user_and_assistant_text(self):
        messages = [
            UserMessage(role="user", content="How do I deploy?", timestamp=1000),
            _make_assistant_msg("Use docker compose up."),
            UserMessage(role="user", content="What about volumes?", timestamp=2000),
            _make_assistant_msg("Mount /data as a volume."),
        ]
        text = extract_conversation_text(messages)
        assert "How do I deploy?" in text
        assert "Use docker compose up." in text
        assert "What about volumes?" in text
        assert "Mount /data as a volume." in text

    def test_empty_messages_returns_empty(self):
        assert extract_conversation_text([]) == ""

    def test_truncates_to_max_messages(self):
        messages = [
            UserMessage(role="user", content=f"msg-{i}", timestamp=i * 1000)
            for i in range(100)
        ]
        text = extract_conversation_text(messages, max_messages=5)
        assert "msg-95" in text
        assert "msg-99" in text
        assert "msg-0" not in text

    def test_with_topic_hint(self):
        messages = [
            UserMessage(role="user", content="Hello", timestamp=1000),
            _make_assistant_msg("Hi there!"),
        ]
        text = extract_conversation_text(messages, topic_hint="deployment")
        assert "deployment" in text.lower() or "Hello" in text


def _make_assistant_msg(text: str) -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text=text)],
        api="test",
        provider="test",
        model="test-model",
        timestamp=1000,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )


class TestFormatSkillMd:
    """Tests for format_skill_md."""

    def test_formats_correctly(self):
        draft = SkillDraft(
            name="my-skill",
            description="A useful skill",
            body="# My Skill\n\nStep 1: Do stuff.",
        )
        md = format_skill_md(draft)
        assert md.startswith("---\n")
        assert "name: my-skill" in md
        assert "description: A useful skill" in md
        assert "---" in md
        assert "# My Skill" in md
        assert "Step 1: Do stuff." in md


class TestGenerateSkillDraft:
    """Tests for generate_skill_draft (mocked LLM)."""

    @pytest.mark.asyncio
    async def test_generates_valid_draft(self):
        mock_response = _make_assistant_msg(
            '{"name": "deploy-guide", "description": "How to deploy with Docker", "body": "# Deploy Guide\\n\\nUse docker compose."}'
        )
        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            mock_model = MagicMock()
            draft = await generate_skill_draft(
                mock_model, "User asked about Docker deployment."
            )
            assert draft.name == "deploy-guide"
            assert "Docker" in draft.description
            assert "docker compose" in draft.body

    @pytest.mark.asyncio
    async def test_sanitizes_invalid_name_from_llm(self):
        mock_response = _make_assistant_msg(
            '{"name": "Invalid Name!", "description": "Some desc", "body": "# Body"}'
        )
        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            mock_model = MagicMock()
            draft = await generate_skill_draft(mock_model, "Some conversation.")
            assert _NAME_RE.match(draft.name)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestExtractConversationText -v`
Expected: FAIL with `ImportError: cannot import name 'extract_conversation_text'`

**Step 3: Write implementation**

Add to `packages/basket-assistant/basket_assistant/commands/create_skill.py`:

```python
import json
import logging
from pathlib import Path
from typing import List, Optional

from basket_ai.api import complete
from basket_ai.types import AssistantMessage, Context, Message, TextContent, UserMessage

logger = logging.getLogger(__name__)

_GENERATION_SYSTEM_PROMPT = """You are a skill generator. Given a conversation summary, create a reusable skill document.

Respond with a JSON object (no markdown fences) containing exactly these fields:
- "name": lowercase alphanumeric with hyphens only (e.g. "docker-deploy"), max 64 chars
- "description": one-line description of what this skill teaches (max 200 chars)
- "body": Markdown body with sections like ## Overview, ## Steps, ## Examples

Focus on extracting actionable knowledge, patterns, and step-by-step instructions.
Make the skill self-contained so someone can follow it without the original conversation."""


def extract_conversation_text(
    messages: List[Message],
    *,
    max_messages: int = 50,
    topic_hint: Optional[str] = None,
) -> str:
    """
    Extract text from conversation messages for summarization.

    Args:
        messages: List of conversation messages
        max_messages: Maximum messages to include (takes most recent)
        topic_hint: Optional topic to focus extraction on

    Returns:
        Formatted conversation text
    """
    if not messages:
        return ""

    # Take most recent N messages
    recent = messages[-max_messages:]

    lines: List[str] = []
    if topic_hint:
        lines.append(f"[Topic focus: {topic_hint}]")
        lines.append("")

    for msg in recent:
        role = getattr(msg, "role", "unknown")
        content = getattr(msg, "content", "")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            for block in content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            text = "\n".join(text_parts)
        else:
            text = str(content)

        if text.strip():
            lines.append(f"[{role}]: {text.strip()}")
            lines.append("")

    return "\n".join(lines).strip()


def format_skill_md(draft: SkillDraft) -> str:
    """Format a SkillDraft as a SKILL.md file content string."""
    return f"""---
name: {draft.name}
description: {draft.description}
---

{draft.body}
"""


async def generate_skill_draft(
    model,
    conversation_text: str,
    topic_hint: Optional[str] = None,
) -> SkillDraft:
    """
    Call LLM to generate a SkillDraft from conversation text.

    Args:
        model: The LLM model instance
        conversation_text: Extracted conversation text
        topic_hint: Optional topic hint for focused generation

    Returns:
        Validated SkillDraft

    Raises:
        ValueError: If LLM response cannot be parsed into a valid SkillDraft
    """
    user_prompt = f"Create a skill from this conversation:\n\n{conversation_text}"
    if topic_hint:
        user_prompt = f"Focus on the topic: {topic_hint}\n\n{user_prompt}"

    import time

    context = Context(
        systemPrompt=_GENERATION_SYSTEM_PROMPT,
        messages=[
            UserMessage(
                role="user",
                content=user_prompt,
                timestamp=int(time.time() * 1000),
            )
        ],
    )

    response: AssistantMessage = await complete(model, context)

    # Extract text from response
    response_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            response_text += block.text

    # Parse JSON response
    try:
        data = json.loads(response_text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Sanitize name if needed
    raw_name = data.get("name", "")
    if not _NAME_RE.match(raw_name):
        raw_name = sanitize_skill_name(raw_name)

    return SkillDraft(
        name=raw_name,
        description=data.get("description", ""),
        body=data.get("body", ""),
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/create_skill.py packages/basket-assistant/tests/test_create_skill.py
git commit -m "feat: add conversation extraction and SKILL.md generation"
```

---

### Task 3: Implement save_skill_to_disk function

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Write failing tests for save_skill_to_disk**

Append to `packages/basket-assistant/tests/test_create_skill.py`:

```python
from basket_assistant.commands.create_skill import save_skill_to_disk, SkillScope


class TestSaveSkillToDisk:
    """Tests for save_skill_to_disk."""

    def test_saves_to_project_scope(self, tmp_path):
        draft = SkillDraft(
            name="my-skill",
            description="A test skill",
            body="# My Skill\n\nSome content.",
        )
        result = save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=tmp_path)
        assert result.exists()
        assert result.name == "SKILL.md"
        assert result.parent.name == "my-skill"
        content = result.read_text(encoding="utf-8")
        assert "name: my-skill" in content
        assert "description: A test skill" in content
        assert "# My Skill" in content

    def test_saves_to_global_scope(self, tmp_path):
        draft = SkillDraft(
            name="global-skill",
            description="A global skill",
            body="# Global\n\nContent.",
        )
        result = save_skill_to_disk(draft, SkillScope.GLOBAL, global_skills_dir=tmp_path)
        assert result.exists()
        assert result.parent.name == "global-skill"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "nested" / "deep"
        draft = SkillDraft(
            name="nested-skill",
            description="Nested",
            body="# Body",
        )
        result = save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=target)
        assert result.exists()

    def test_conflict_raises_when_exists(self, tmp_path):
        (tmp_path / "existing-skill").mkdir()
        (tmp_path / "existing-skill" / "SKILL.md").write_text("old", encoding="utf-8")
        draft = SkillDraft(
            name="existing-skill",
            description="New version",
            body="# New",
        )
        with pytest.raises(FileExistsError):
            save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=tmp_path)

    def test_overwrite_when_forced(self, tmp_path):
        (tmp_path / "existing-skill").mkdir()
        (tmp_path / "existing-skill" / "SKILL.md").write_text("old", encoding="utf-8")
        draft = SkillDraft(
            name="existing-skill",
            description="New version",
            body="# New",
        )
        result = save_skill_to_disk(
            draft, SkillScope.PROJECT, project_skills_dir=tmp_path, overwrite=True
        )
        assert "New version" in result.read_text(encoding="utf-8")
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestSaveSkillToDisk -v`
Expected: FAIL with `ImportError: cannot import name 'save_skill_to_disk'`

**Step 3: Write implementation**

Add to `packages/basket-assistant/basket_assistant/commands/create_skill.py`:

```python
def save_skill_to_disk(
    draft: SkillDraft,
    scope: SkillScope,
    *,
    project_skills_dir: Optional[Path] = None,
    global_skills_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> Path:
    """
    Write a SkillDraft to disk as a SKILL.md file.

    Args:
        draft: The validated skill draft
        scope: Where to save (project or global)
        project_skills_dir: Project-level skills directory
        global_skills_dir: Global-level skills directory
        overwrite: If True, overwrite existing skill

    Returns:
        Path to the created SKILL.md file

    Raises:
        FileExistsError: If skill directory already exists and overwrite is False
        ValueError: If target directory is not provided for the chosen scope
    """
    if scope == SkillScope.PROJECT:
        base_dir = project_skills_dir or Path.cwd() / ".basket" / "skills"
    else:
        base_dir = global_skills_dir or Path.home() / ".basket" / "skills"

    skill_dir = base_dir / draft.name
    skill_md_path = skill_dir / "SKILL.md"

    if skill_dir.exists() and not overwrite:
        raise FileExistsError(
            f"Skill directory already exists: {skill_dir}. Use overwrite=True to replace."
        )

    # Create directories
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Write SKILL.md
    content = format_skill_md(draft)
    skill_md_path.write_text(content, encoding="utf-8")

    return skill_md_path
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestSaveSkillToDisk -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/create_skill.py packages/basket-assistant/tests/test_create_skill.py
git commit -m "feat: add save_skill_to_disk for /create-skill"
```

---

### Task 4: Register the /create-skill command handler

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py`
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Write failing integration test for the command handler**

Append to `packages/basket-assistant/tests/test_create_skill.py`:

```python
from basket_assistant.commands.create_skill import handle_create_skill


class TestHandleCreateSkill:
    """Integration tests for the /create-skill command handler."""

    @pytest.mark.asyncio
    async def test_empty_session_returns_error(self):
        """When session has no messages, return error."""
        mock_agent = _build_mock_agent(messages=[])
        success, msg = await handle_create_skill(mock_agent, "")
        assert not success
        assert "empty" in msg.lower() or "没有" in msg.lower() or "no" in msg.lower()

    @pytest.mark.asyncio
    async def test_generates_and_returns_preview(self):
        """When session has messages, generates a draft and returns preview."""
        messages = [
            UserMessage(role="user", content="How do I deploy?", timestamp=1000),
            _make_assistant_msg("Use docker compose."),
        ]
        mock_agent = _build_mock_agent(messages=messages)

        llm_response = _make_assistant_msg(
            '{"name": "docker-deploy", "description": "Docker deployment guide", "body": "# Docker Deploy\\n\\nUse docker compose up."}'
        )
        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            success, msg = await handle_create_skill(mock_agent, "")
            assert success
            assert "docker-deploy" in msg


def _build_mock_agent(messages=None):
    """Build a mock agent with session and model."""
    agent = MagicMock()
    agent.session_manager = MagicMock()
    agent._session_id = "test-session-id"
    agent.session_manager.load_messages = AsyncMock(return_value=messages or [])
    agent.model = MagicMock()
    agent.settings = MagicMock()
    agent.settings.skills_dirs = []
    agent.settings.skills_include = []
    return agent
```

**Step 2: Run test to verify it fails**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestHandleCreateSkill -v`
Expected: FAIL with `ImportError: cannot import name 'handle_create_skill'`

**Step 3: Write the command handler**

Add to `packages/basket-assistant/basket_assistant/commands/create_skill.py`:

```python
from typing import Tuple


async def handle_create_skill(agent, args: str) -> Tuple[bool, str]:
    """
    Handle /create-skill command.

    Flow:
    1. Load session messages
    2. Extract conversation text
    3. Generate skill draft via LLM
    4. Return preview for user to confirm

    Args:
        agent: The AssistantAgent instance
        args: Optional topic hint string

    Returns:
        Tuple of (success, message_to_display)
    """
    topic_hint = args.strip() or None

    # Check session
    if agent.session_manager is None or agent._session_id is None:
        return False, "No active session. Cannot create skill."

    # Load messages
    messages = await agent.session_manager.load_messages(agent._session_id)
    if not messages:
        return False, "Current session has no conversation history. Cannot generate skill."

    # Extract conversation text
    conversation_text = extract_conversation_text(
        messages, topic_hint=topic_hint
    )

    if not conversation_text.strip():
        return False, "No usable conversation text found."

    # Generate draft
    try:
        draft = await generate_skill_draft(
            agent.model, conversation_text, topic_hint=topic_hint
        )
    except (ValueError, Exception) as e:
        return False, f"Failed to generate skill draft: {e}"

    # Format preview
    preview = format_skill_md(draft)
    preview_display = (
        f"📝 Skill draft generated:\n"
        f"  Name: {draft.name}\n"
        f"  Description: {draft.description}\n"
        f"{'─' * 40}\n"
        f"{preview}\n"
        f"{'─' * 40}\n"
        f"Use '/save-skill {draft.name}' to save, or '/create-skill' to regenerate."
    )

    # Store draft on agent for subsequent /save-skill command
    agent._pending_skill_draft = draft

    return True, preview_display
```

**Step 4: Register the command in handlers.py**

Modify `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py`:

At the end of `register_builtin_commands()` function (after line 231), add:

```python
    # Register /create-skill command
    from basket_assistant.commands.create_skill import handle_create_skill

    async def _handle_create_skill(args: str) -> tuple[bool, str]:
        return await handle_create_skill(agent, args)

    registry.register(
        name="create-skill",
        handler=_handle_create_skill,
        description="Create a skill from conversation content",
        usage="/create-skill [topic hint]",
        aliases=["create-skill", "/create-skill"],
    )
```

Also update the help text in `handle_help` to include the new command (modify line 31-42):

Add this line inside the help text string:
```
  /create-skill [topic] Create a skill from conversation
```

**Step 5: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/create_skill.py packages/basket-assistant/basket_assistant/interaction/commands/handlers.py packages/basket-assistant/tests/test_create_skill.py
git commit -m "feat: register /create-skill command handler"
```

---

### Task 5: Implement /save-skill command with scope selection

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Modify: `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py`
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Write failing tests for handle_save_skill**

Append to `packages/basket-assistant/tests/test_create_skill.py`:

```python
from basket_assistant.commands.create_skill import handle_save_skill


class TestHandleSaveSkill:
    """Tests for /save-skill command."""

    @pytest.mark.asyncio
    async def test_no_pending_draft_returns_error(self):
        agent = _build_mock_agent()
        agent._pending_skill_draft = None
        success, msg = await handle_save_skill(agent, "global")
        assert not success
        assert "no pending" in msg.lower() or "draft" in msg.lower()

    @pytest.mark.asyncio
    async def test_saves_to_global(self, tmp_path):
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="test-skill",
            description="Test",
            body="# Test\n\nBody.",
        )
        # Patch get_skills_dirs and home dir
        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path,
        ), patch(
            "basket_assistant.commands.create_skill._resolve_project_skills_dir",
            return_value=tmp_path / "project",
        ):
            success, msg = await handle_save_skill(agent, "global")
            assert success
            assert "test-skill" in msg
            assert (tmp_path / "test-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_saves_to_project(self, tmp_path):
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="proj-skill",
            description="Project skill",
            body="# Proj\n\nBody.",
        )
        with patch(
            "basket_assistant.commands.create_skill._resolve_project_skills_dir",
            return_value=tmp_path,
        ), patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path / "global",
        ):
            success, msg = await handle_save_skill(agent, "project")
            assert success
            assert (tmp_path / "proj-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_clears_pending_draft_after_save(self, tmp_path):
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="clear-test",
            description="Test clearing",
            body="# Body",
        )
        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path,
        ), patch(
            "basket_assistant.commands.create_skill._resolve_project_skills_dir",
            return_value=tmp_path / "project",
        ):
            await handle_save_skill(agent, "global")
            assert agent._pending_skill_draft is None
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestHandleSaveSkill -v`
Expected: FAIL with `ImportError: cannot import name 'handle_save_skill'`

**Step 3: Write implementation**

Add to `packages/basket-assistant/basket_assistant/commands/create_skill.py`:

```python
def _resolve_global_skills_dir() -> Path:
    """Return the global skills directory path."""
    return Path.home() / ".basket" / "skills"


def _resolve_project_skills_dir() -> Path:
    """Return the project-level skills directory path."""
    return Path.cwd() / ".basket" / "skills"


async def handle_save_skill(agent, args: str) -> Tuple[bool, str]:
    """
    Handle /save-skill command. Saves the pending draft to disk.

    Args:
        agent: The AssistantAgent instance
        args: "global" or "project" (default: prompts user)

    Returns:
        Tuple of (success, message)
    """
    draft = getattr(agent, "_pending_skill_draft", None)
    if draft is None:
        return False, "No pending skill draft. Run /create-skill first."

    # Determine scope
    scope_str = args.strip().lower()
    if scope_str == "global":
        scope = SkillScope.GLOBAL
    elif scope_str == "project":
        scope = SkillScope.PROJECT
    else:
        return False, (
            "Please specify scope: /save-skill global or /save-skill project\n"
            f"  global  → {_resolve_global_skills_dir()}\n"
            f"  project → {_resolve_project_skills_dir()}"
        )

    # Resolve directories
    global_dir = _resolve_global_skills_dir()
    project_dir = _resolve_project_skills_dir()

    try:
        saved_path = save_skill_to_disk(
            draft,
            scope,
            project_skills_dir=project_dir,
            global_skills_dir=global_dir,
        )
    except FileExistsError:
        return False, (
            f"Skill '{draft.name}' already exists. "
            f"Use /save-skill {scope_str} --overwrite to replace."
        )
    except Exception as e:
        return False, f"Failed to save skill: {e}"

    # Clear pending draft
    agent._pending_skill_draft = None

    return True, f"✅ Skill '{draft.name}' saved to {saved_path.parent}\nIt is now available via /skill {draft.name}"
```

**Step 4: Register the /save-skill command**

Add to `register_builtin_commands()` in `handlers.py` (after the /create-skill registration):

```python
    # Register /save-skill command
    from basket_assistant.commands.create_skill import handle_save_skill

    async def _handle_save_skill(args: str) -> tuple[bool, str]:
        return await handle_save_skill(agent, args)

    registry.register(
        name="save-skill",
        handler=_handle_save_skill,
        description="Save pending skill draft to disk",
        usage="/save-skill <global|project>",
        aliases=["save-skill", "/save-skill"],
    )
```

Also add to help text:
```
  /save-skill <scope>  Save generated skill (global/project)
```

**Step 5: Run tests to verify they pass**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add packages/basket-assistant/basket_assistant/commands/create_skill.py packages/basket-assistant/basket_assistant/interaction/commands/handlers.py packages/basket-assistant/tests/test_create_skill.py
git commit -m "feat: add /save-skill command with scope selection"
```

---

### Task 6: Add skills index refresh after save

**Files:**
- Modify: `packages/basket-assistant/basket_assistant/commands/create_skill.py`
- Modify: `packages/basket-assistant/basket_assistant/core/skills_loader.py` (minor: export validation constants)
- Test: `packages/basket-assistant/tests/test_create_skill.py`

**Step 1: Write failing test for refresh after save**

Append to `packages/basket-assistant/tests/test_create_skill.py`:

```python
from basket_assistant.core import get_skills_index


class TestSkillRefreshAfterSave:
    """Test that saved skills appear in the index immediately."""

    def test_saved_skill_appears_in_index(self, tmp_path):
        """After saving, get_skills_index picks up the new skill."""
        draft = SkillDraft(
            name="new-skill",
            description="Brand new",
            body="# New Skill\n\nFresh content.",
        )
        save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=tmp_path)

        # Verify it appears in the index
        index = get_skills_index([tmp_path])
        names = [n for n, _ in index]
        assert "new-skill" in names

    def test_saved_skill_content_loadable(self, tmp_path):
        """After saving, get_skill_full_content returns the body."""
        from basket_assistant.core import get_skill_full_content

        draft = SkillDraft(
            name="loadable-skill",
            description="Can be loaded",
            body="# Loadable\n\nStep 1.",
        )
        save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=tmp_path)

        content = get_skill_full_content("loadable-skill", [tmp_path])
        assert "Loadable" in content
        assert "Step 1" in content
```

**Step 2: Run tests to verify they pass (these should already pass with current implementation)**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py::TestSkillRefreshAfterSave -v`
Expected: PASS (since `get_skills_index` scans directories each time)

**Step 3: Commit**

```bash
git add packages/basket-assistant/tests/test_create_skill.py
git commit -m "test: verify skill index refresh after save"
```

---

### Task 7: Run full test suite and verify coverage

**Files:**
- All test files in `packages/basket-assistant/tests/`

**Step 1: Run all tests in basket-assistant to verify no regressions**

Run: `cd packages/basket-assistant && poetry run pytest -v`
Expected: All existing tests PASS, no regressions

**Step 2: Run new tests with coverage**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_create_skill.py --cov=basket_assistant.commands.create_skill --cov-report=term-missing -v`
Expected: Coverage ≥ 80% for `create_skill.py`

**Step 3: Fix any uncovered lines**

If coverage is below 80%, add tests for uncovered branches (e.g., error paths, edge cases).

**Step 4: Run existing skill tests to verify no conflicts**

Run: `cd packages/basket-assistant && poetry run pytest tests/test_skills.py tests/test_skill_tool.py -v`
Expected: All PASS

**Step 5: Commit any additional tests**

```bash
git add packages/basket-assistant/tests/
git commit -m "test: ensure 80%+ coverage for create-skill command"
```

---

### Task 8: Final cleanup and type checking

**Files:**
- `packages/basket-assistant/basket_assistant/commands/create_skill.py`

**Step 1: Run type checker**

Run: `cd packages/basket-assistant && poetry run mypy basket_assistant/commands/create_skill.py --ignore-missing-imports`
Expected: No type errors

**Step 2: Run formatter**

Run: `cd packages/basket-assistant && poetry run black basket_assistant/commands/ tests/test_create_skill.py`
Expected: Files formatted

**Step 3: Run linter**

Run: `cd packages/basket-assistant && poetry run ruff check basket_assistant/commands/ tests/test_create_skill.py`
Expected: No lint errors

**Step 4: Fix any issues found**

**Step 5: Final commit**

```bash
git add -u
git commit -m "chore: type checking, formatting, and lint for /create-skill"
```

---

## Summary of all files created/modified

### Created:
- `packages/basket-assistant/basket_assistant/commands/__init__.py` — Package init
- `packages/basket-assistant/basket_assistant/commands/create_skill.py` — Core implementation (~200 lines)
- `packages/basket-assistant/tests/test_create_skill.py` — Tests (~200 lines)

### Modified:
- `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py` — Register `/create-skill` and `/save-skill` commands, update help text

### Not modified (leveraged as-is):
- `basket_assistant/core/skills_loader.py` — Already scans directories dynamically, no changes needed
- `basket_assistant/tools/skill.py` — Skill tool picks up new skills via `dirs_getter()` lambda
