"""Tests for /create-skill command."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from basket_ai.types import (
    AssistantMessage,
    StopReason,
    TextContent,
    UserMessage,
)
from basket_assistant.commands.create_skill import (
    SkillDraft,
    SkillScope,
    extract_conversation_text,
    format_skill_md,
    generate_skill_draft,
    handle_create_skill,
    handle_save_skill,
    sanitize_skill_name,
    save_skill_to_disk,
)
from basket_assistant.core import get_skill_full_content, get_skills_index


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


# ---------------------------------------------------------------------------
# Helpers for building test messages
# ---------------------------------------------------------------------------

def _user_msg(text: str, ts: int = 1000) -> UserMessage:
    return UserMessage(role="user", content=text, timestamp=ts)


def _assistant_msg(text: str, ts: int = 1001) -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text=text)],
        api="test-api",
        provider="test-provider",
        model="test-model",
        stopReason=StopReason.STOP,
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Tests for extract_conversation_text
# ---------------------------------------------------------------------------


class TestExtractConversationText:
    """Tests for extract_conversation_text."""

    def test_extracts_user_and_assistant_text(self):
        messages = [
            _user_msg("How do I deploy Docker?"),
            _assistant_msg("Here are the steps..."),
        ]
        result = extract_conversation_text(messages)
        assert "How do I deploy Docker?" in result
        assert "Here are the steps..." in result

    def test_empty_messages_returns_empty(self):
        result = extract_conversation_text([])
        assert result == ""

    def test_truncates_to_max_messages(self):
        messages = [_user_msg(f"msg-{i}", ts=1000 + i) for i in range(10)]
        result = extract_conversation_text(messages, max_messages=3)
        # Should only contain the last 3 messages
        assert "msg-7" in result
        assert "msg-8" in result
        assert "msg-9" in result
        assert "msg-0" not in result

    def test_with_topic_hint(self):
        messages = [_user_msg("hello")]
        result = extract_conversation_text(messages, topic_hint="Docker deployment")
        assert "Docker deployment" in result


# ---------------------------------------------------------------------------
# Tests for format_skill_md
# ---------------------------------------------------------------------------


class TestFormatSkillMd:
    """Tests for format_skill_md."""

    def test_formats_correctly(self):
        draft = SkillDraft(
            name="docker-deploy",
            description="How to deploy with Docker",
            body="## Overview\n\nUse docker compose.",
        )
        result = format_skill_md(draft)
        # YAML frontmatter
        assert result.startswith("---\n")
        assert "name: docker-deploy" in result
        assert 'description: "How to deploy with Docker"' in result
        # Body after frontmatter closing ---
        parts = result.split("---\n")
        # parts[0] is empty (before first ---), parts[1] is YAML, parts[2:] is body
        body_section = "---\n".join(parts[2:])
        assert "## Overview" in body_section
        assert "Use docker compose." in body_section


# ---------------------------------------------------------------------------
# Tests for generate_skill_draft
# ---------------------------------------------------------------------------


class TestGenerateSkillDraft:
    """Tests for generate_skill_draft."""

    @pytest.mark.asyncio
    async def test_generates_valid_draft(self):
        llm_response_json = json.dumps({
            "name": "docker-deploy",
            "description": "Deploy apps with Docker",
            "body": "## Overview\n\nStep-by-step Docker deployment.",
        })
        mock_message = _assistant_msg(llm_response_json)

        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_message,
        ):
            draft = await generate_skill_draft(
                model="fake-model",
                conversation_text="User asked about Docker.",
            )

        assert isinstance(draft, SkillDraft)
        assert draft.name == "docker-deploy"
        assert draft.description == "Deploy apps with Docker"
        assert "Step-by-step" in draft.body

    @pytest.mark.asyncio
    async def test_sanitizes_invalid_name_from_llm(self):
        llm_response_json = json.dumps({
            "name": "Docker Deploy!!",
            "description": "Deploy apps with Docker",
            "body": "## Overview\n\nSome body.",
        })
        mock_message = _assistant_msg(llm_response_json)

        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_message,
        ):
            draft = await generate_skill_draft(
                model="fake-model",
                conversation_text="User asked about Docker.",
            )

        assert isinstance(draft, SkillDraft)
        # The invalid name should have been sanitized
        assert draft.name == "docker-deploy"

    @pytest.mark.asyncio
    async def test_raises_on_no_text_content(self):
        """LLM returns an AssistantMessage with no TextContent blocks."""
        empty_message = AssistantMessage(
            role="assistant",
            content=[],  # No TextContent blocks at all
            api="test-api",
            provider="test-provider",
            model="test-model",
            stopReason=StopReason.STOP,
            timestamp=1001,
        )

        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=empty_message,
        ):
            with pytest.raises(ValueError, match="LLM returned no text content"):
                await generate_skill_draft(
                    model="fake-model",
                    conversation_text="User asked something.",
                )

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self):
        """LLM returns text that is not valid JSON."""
        mock_message = _assistant_msg("This is not JSON at all {{{")

        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_message,
        ):
            with pytest.raises(ValueError, match="LLM returned invalid JSON"):
                await generate_skill_draft(
                    model="fake-model",
                    conversation_text="User asked something.",
                )

    @pytest.mark.asyncio
    async def test_raises_on_missing_required_field(self):
        """LLM returns valid JSON but missing the 'body' field."""
        incomplete_json = json.dumps({
            "name": "some-skill",
            "description": "A skill description",
            # "body" is intentionally missing
        })
        mock_message = _assistant_msg(incomplete_json)

        with patch(
            "basket_assistant.commands.create_skill.complete",
            new_callable=AsyncMock,
            return_value=mock_message,
        ):
            with pytest.raises(ValueError, match="missing required field.*'body'"):
                await generate_skill_draft(
                    model="fake-model",
                    conversation_text="User asked something.",
                )


# ---------------------------------------------------------------------------
# Tests for save_skill_to_disk
# ---------------------------------------------------------------------------


def _make_draft(
    name: str = "test-skill",
    description: str = "A test skill",
    body: str = "## Overview\n\nTest body.",
) -> SkillDraft:
    return SkillDraft(name=name, description=description, body=body)


class TestSaveSkillToDisk:
    """Tests for save_skill_to_disk."""

    def test_saves_to_project_scope(self, tmp_path):
        """Save with PROJECT scope writes SKILL.md under project_skills_dir."""
        draft = _make_draft()
        result = save_skill_to_disk(
            draft,
            SkillScope.PROJECT,
            project_skills_dir=tmp_path,
        )

        expected_path = tmp_path / "test-skill" / "SKILL.md"
        assert result == expected_path
        assert expected_path.exists()
        content = expected_path.read_text()
        assert "name: test-skill" in content
        assert "A test skill" in content
        assert "## Overview" in content

    def test_saves_to_global_scope(self, tmp_path):
        """Save with GLOBAL scope writes SKILL.md under global_skills_dir."""
        draft = _make_draft(name="global-skill")
        result = save_skill_to_disk(
            draft,
            SkillScope.GLOBAL,
            global_skills_dir=tmp_path,
        )

        expected_path = tmp_path / "global-skill" / "SKILL.md"
        assert result == expected_path
        assert expected_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        """Creates deeply nested parent directories that don't exist yet."""
        nested_dir = tmp_path / "deeply" / "nested" / "skills"
        draft = _make_draft()
        result = save_skill_to_disk(
            draft,
            SkillScope.PROJECT,
            project_skills_dir=nested_dir,
        )

        expected_path = nested_dir / "test-skill" / "SKILL.md"
        assert result == expected_path
        assert expected_path.exists()

    def test_conflict_raises_when_exists(self, tmp_path):
        """Raises FileExistsError when skill directory already exists and overwrite is False."""
        draft = _make_draft()
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("existing content")

        with pytest.raises(FileExistsError):
            save_skill_to_disk(
                draft,
                SkillScope.PROJECT,
                project_skills_dir=tmp_path,
                overwrite=False,
            )

    def test_overwrite_when_forced(self, tmp_path):
        """Overwrites existing SKILL.md when overwrite=True."""
        draft_v1 = _make_draft(description="Version 1")
        draft_v2 = _make_draft(description="Version 2")

        # Save v1
        save_skill_to_disk(
            draft_v1,
            SkillScope.PROJECT,
            project_skills_dir=tmp_path,
        )

        # Save v2 with overwrite
        result = save_skill_to_disk(
            draft_v2,
            SkillScope.PROJECT,
            project_skills_dir=tmp_path,
            overwrite=True,
        )

        content = result.read_text()
        assert "Version 2" in content
        assert "Version 1" not in content


# ---------------------------------------------------------------------------
# Helper for building mock agents
# ---------------------------------------------------------------------------


def _build_mock_agent(messages=None):
    """Build a mock agent with session_manager and model for handler tests."""
    agent = MagicMock()
    agent.session_manager = MagicMock()
    agent._session_id = "test-session-id"
    agent.session_manager.load_messages = AsyncMock(return_value=messages or [])
    agent.model = MagicMock()
    agent._pending_skill_draft = None
    return agent


# ---------------------------------------------------------------------------
# Tests for handle_create_skill
# ---------------------------------------------------------------------------


class TestHandleCreateSkill:
    """Tests for handle_create_skill command handler."""

    @pytest.mark.asyncio
    async def test_no_session_manager_returns_error(self):
        """Returns error when session_manager is None."""
        agent = _build_mock_agent()
        agent.session_manager = None
        success, msg = await handle_create_skill(agent, "")
        assert not success
        assert "No active session" in msg

    @pytest.mark.asyncio
    async def test_no_session_id_returns_error(self):
        """Returns error when _session_id is None."""
        agent = _build_mock_agent()
        agent._session_id = None
        success, msg = await handle_create_skill(agent, "")
        assert not success
        assert "No active session" in msg

    @pytest.mark.asyncio
    async def test_empty_messages_returns_error(self):
        """Returns error when session has no messages."""
        agent = _build_mock_agent(messages=[])
        success, msg = await handle_create_skill(agent, "")
        assert not success
        assert "no conversation history" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_usable_text_returns_error(self):
        """Returns error when messages yield no usable text."""
        # SystemMessage or other non-user/assistant messages produce empty text
        agent = _build_mock_agent(messages=[MagicMock()])
        # extract_conversation_text skips unknown types → empty string
        success, msg = await handle_create_skill(agent, "")
        assert not success
        assert "No usable conversation text" in msg

    @pytest.mark.asyncio
    async def test_generates_and_returns_preview(self):
        """Successfully generates a skill draft and returns preview."""
        messages = [
            _user_msg("How do I deploy Docker?"),
            _assistant_msg("Here are the steps to deploy with Docker."),
        ]
        agent = _build_mock_agent(messages=messages)

        mock_draft = SkillDraft(
            name="docker-deploy",
            description="Deploy apps with Docker",
            body="## Overview\n\nStep-by-step deployment.",
        )

        with patch(
            "basket_assistant.commands.create_skill.generate_skill_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ):
            success, msg = await handle_create_skill(agent, "docker")

        assert success
        assert "docker-deploy" in msg
        assert "Deploy apps with Docker" in msg
        assert "/save-skill" in msg
        assert agent._pending_skill_draft == mock_draft

    @pytest.mark.asyncio
    async def test_generation_failure_returns_error(self):
        """Returns error when generate_skill_draft raises."""
        messages = [_user_msg("something")]
        agent = _build_mock_agent(messages=messages)

        with patch(
            "basket_assistant.commands.create_skill.generate_skill_draft",
            new_callable=AsyncMock,
            side_effect=ValueError("LLM returned invalid JSON"),
        ):
            success, msg = await handle_create_skill(agent, "")

        assert not success
        assert "Failed to generate skill draft" in msg

    @pytest.mark.asyncio
    async def test_topic_hint_passed_through(self):
        """Topic hint from args is forwarded to generate_skill_draft."""
        messages = [_user_msg("hello")]
        agent = _build_mock_agent(messages=messages)

        mock_draft = SkillDraft(
            name="test-skill",
            description="A test skill",
            body="# Test",
        )

        with patch(
            "basket_assistant.commands.create_skill.generate_skill_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ) as mock_gen:
            await handle_create_skill(agent, "  my topic  ")

        mock_gen.assert_awaited_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs[1].get("topic_hint") == "my topic" or call_kwargs.kwargs.get("topic_hint") == "my topic"


# ---------------------------------------------------------------------------
# Tests for handle_save_skill
# ---------------------------------------------------------------------------


class TestHandleSaveSkill:
    """Tests for handle_save_skill command handler."""

    @pytest.mark.asyncio
    async def test_no_pending_draft_returns_error(self):
        """Returns error when no pending skill draft exists."""
        agent = _build_mock_agent()
        agent._pending_skill_draft = None
        success, msg = await handle_save_skill(agent, "global")
        assert not success
        assert "No pending skill draft" in msg

    @pytest.mark.asyncio
    async def test_invalid_scope_returns_error(self):
        """Returns error for invalid scope argument."""
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="test-skill", description="A test", body="# Test"
        )
        success, msg = await handle_save_skill(agent, "invalid")
        assert not success
        assert "Please specify scope" in msg

    @pytest.mark.asyncio
    async def test_empty_scope_returns_error(self):
        """Returns error when scope argument is empty."""
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="test-skill", description="A test", body="# Test"
        )
        success, msg = await handle_save_skill(agent, "")
        assert not success
        assert "Please specify scope" in msg

    @pytest.mark.asyncio
    async def test_saves_to_global(self, tmp_path):
        """Saves skill to global skills directory."""
        agent = _build_mock_agent()
        draft = SkillDraft(
            name="test-skill", description="A test skill", body="# Test\n\nBody."
        )
        agent._pending_skill_draft = draft

        global_dir = tmp_path / "global-skills"

        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=global_dir,
        ):
            success, msg = await handle_save_skill(agent, "global")

        assert success
        assert "test-skill" in msg
        assert (global_dir / "test-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_saves_to_project(self, tmp_path):
        """Saves skill to project skills directory."""
        agent = _build_mock_agent()
        draft = SkillDraft(
            name="proj-skill", description="A project skill", body="# Proj"
        )
        agent._pending_skill_draft = draft

        project_dir = tmp_path / "project-skills"

        with patch(
            "basket_assistant.commands.create_skill._resolve_project_skills_dir",
            return_value=project_dir,
        ):
            success, msg = await handle_save_skill(agent, "project")

        assert success
        assert "proj-skill" in msg
        assert (project_dir / "proj-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_clears_pending_after_save(self, tmp_path):
        """Clears _pending_skill_draft after successful save."""
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="clear-test", description="Test clearing", body="# Body"
        )

        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            success, _ = await handle_save_skill(agent, "global")

        assert success
        assert agent._pending_skill_draft is None

    @pytest.mark.asyncio
    async def test_file_exists_returns_error(self, tmp_path):
        """Returns error when skill directory already exists."""
        agent = _build_mock_agent()
        draft = SkillDraft(
            name="existing-skill", description="Already exists", body="# Body"
        )
        agent._pending_skill_draft = draft

        # Pre-create the directory to trigger FileExistsError
        skill_dir = tmp_path / "existing-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("existing")

        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            success, msg = await handle_save_skill(agent, "global")

        assert not success
        assert "already exists" in msg

    @pytest.mark.asyncio
    async def test_scope_case_insensitive(self, tmp_path):
        """Scope argument is case-insensitive."""
        agent = _build_mock_agent()
        agent._pending_skill_draft = SkillDraft(
            name="case-test", description="Test case", body="# Body"
        )

        with patch(
            "basket_assistant.commands.create_skill._resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            success, _ = await handle_save_skill(agent, "GLOBAL")

        assert success


# ---------------------------------------------------------------------------
# Tests for skill index refresh after save
# ---------------------------------------------------------------------------


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
        index = get_skills_index([tmp_path])
        names = [n for n, _ in index]
        assert "new-skill" in names

    def test_saved_skill_content_loadable(self, tmp_path):
        """After saving, get_skill_full_content returns the body."""
        draft = SkillDraft(
            name="loadable-skill",
            description="Can be loaded",
            body="# Loadable\n\nStep 1.",
        )
        save_skill_to_disk(draft, SkillScope.PROJECT, project_skills_dir=tmp_path)
        content = get_skill_full_content("loadable-skill", [tmp_path])
        assert "Loadable" in content
        assert "Step 1" in content
