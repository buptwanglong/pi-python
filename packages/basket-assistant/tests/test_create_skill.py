"""Tests for skill authoring (core + AgentContext callbacks + tools)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from basket_ai.types import (
    AssistantMessage,
    StopReason,
    TextContent,
    UserMessage,
)
from basket_assistant.core import get_skill_full_content, get_skills_index
from basket_assistant.skills.authoring import (
    SkillDraft,
    SkillScope,
    extract_conversation_text,
    format_skill_md,
    generate_skill_draft,
    sanitize_skill_name,
    save_skill_to_disk,
)
from pydantic import ValidationError


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
        llm_response_json = json.dumps(
            {
                "name": "docker-deploy",
                "description": "Deploy apps with Docker",
                "body": "## Overview\n\nStep-by-step Docker deployment.",
            }
        )
        mock_message = _assistant_msg(llm_response_json)

        with patch(
            "basket_assistant.skills.authoring.complete",
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
        llm_response_json = json.dumps(
            {
                "name": "Docker Deploy!!",
                "description": "Deploy apps with Docker",
                "body": "## Overview\n\nSome body.",
            }
        )
        mock_message = _assistant_msg(llm_response_json)

        with patch(
            "basket_assistant.skills.authoring.complete",
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
            "basket_assistant.skills.authoring.complete",
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
            "basket_assistant.skills.authoring.complete",
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
        incomplete_json = json.dumps(
            {
                "name": "some-skill",
                "description": "A skill description",
                # "body" is intentionally missing
            }
        )
        mock_message = _assistant_msg(incomplete_json)

        with patch(
            "basket_assistant.skills.authoring.complete",
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
# Tests for AgentContext draft / save callbacks (used by tools)
# ---------------------------------------------------------------------------


class TestDraftSkillFromSessionCallback:
    """Tests for ctx.draft_skill_from_session."""

    @pytest.mark.asyncio
    async def test_no_session_manager_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent.session_manager = None
        agent._session_id = "sid"
        ctx = agent.build_tool_context()
        msg = await ctx.draft_skill_from_session(None)
        assert msg.startswith("Error:")
        assert "No active session" in msg

    @pytest.mark.asyncio
    async def test_no_session_id_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = None
        ctx = agent.build_tool_context()
        msg = await ctx.draft_skill_from_session(None)
        assert "No active session" in msg

    @pytest.mark.asyncio
    async def test_empty_messages_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = "sid"
        agent.session_manager.load_messages = AsyncMock(return_value=[])
        ctx = agent.build_tool_context()
        msg = await ctx.draft_skill_from_session(None)
        assert "no conversation history" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_usable_text_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = "sid"
        agent.session_manager.load_messages = AsyncMock(return_value=[MagicMock()])
        ctx = agent.build_tool_context()
        msg = await ctx.draft_skill_from_session(None)
        assert "No usable conversation text" in msg

    @pytest.mark.asyncio
    async def test_generates_and_returns_preview(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = "sid"
        messages = [
            _user_msg("How do I deploy Docker?"),
            _assistant_msg("Here are the steps to deploy with Docker."),
        ]
        agent.session_manager.load_messages = AsyncMock(return_value=messages)

        mock_draft = SkillDraft(
            name="docker-deploy",
            description="Deploy apps with Docker",
            body="## Overview\n\nStep-by-step deployment.",
        )

        with patch(
            "basket_assistant.skills.authoring.generate_skill_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.draft_skill_from_session("docker")

        assert "docker-deploy" in msg
        assert "Deploy apps with Docker" in msg
        assert "save_pending_skill_draft" in msg
        assert agent._pending_skill_draft == mock_draft

    @pytest.mark.asyncio
    async def test_generation_failure_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = "sid"
        agent.session_manager.load_messages = AsyncMock(return_value=[_user_msg("something")])
        with patch(
            "basket_assistant.skills.authoring.generate_skill_draft",
            new_callable=AsyncMock,
            side_effect=ValueError("LLM returned invalid JSON"),
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.draft_skill_from_session(None)
        assert msg.startswith("Error:")
        assert "Failed to generate skill draft" in msg

    @pytest.mark.asyncio
    async def test_topic_hint_passed_through(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._session_id = "sid"
        agent.session_manager.load_messages = AsyncMock(return_value=[_user_msg("hello")])

        mock_draft = SkillDraft(
            name="test-skill",
            description="A test skill",
            body="# Test",
        )

        with patch(
            "basket_assistant.skills.authoring.generate_skill_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ) as mock_gen:
            ctx = agent.build_tool_context()
            await ctx.draft_skill_from_session("  my topic  ")

        mock_gen.assert_awaited_once()
        hint = mock_gen.call_args.kwargs.get("topic_hint")
        assert hint == "my topic"


class TestSavePendingSkillDraftCallback:
    """Tests for ctx.save_pending_skill_draft."""

    @pytest.mark.asyncio
    async def test_no_pending_draft_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._pending_skill_draft = None
        ctx = agent.build_tool_context()
        msg = await ctx.save_pending_skill_draft("global")
        assert msg.startswith("Error:")
        assert "No pending skill draft" in msg

    @pytest.mark.asyncio
    async def test_invalid_scope_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._pending_skill_draft = SkillDraft(
            name="test-skill", description="A test", body="# Test"
        )
        ctx = agent.build_tool_context()
        msg = await ctx.save_pending_skill_draft("invalid")
        assert msg.startswith("Error:")
        assert "scope must be" in msg

    @pytest.mark.asyncio
    async def test_empty_scope_returns_error(self, mock_coding_agent):
        agent = mock_coding_agent
        agent._pending_skill_draft = SkillDraft(
            name="test-skill", description="A test", body="# Test"
        )
        ctx = agent.build_tool_context()
        msg = await ctx.save_pending_skill_draft("")
        assert msg.startswith("Error:")
        assert "scope must be" in msg

    @pytest.mark.asyncio
    async def test_saves_to_global(self, mock_coding_agent, tmp_path):
        agent = mock_coding_agent
        draft = SkillDraft(name="test-skill", description="A test skill", body="# Test\n\nBody.")
        agent._pending_skill_draft = draft

        global_dir = tmp_path / "global-skills"

        with patch(
            "basket_assistant.skills.authoring.resolve_global_skills_dir",
            return_value=global_dir,
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.save_pending_skill_draft("global")

        assert "test-skill" in msg
        assert (global_dir / "test-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_saves_to_project(self, mock_coding_agent, tmp_path):
        agent = mock_coding_agent
        draft = SkillDraft(name="proj-skill", description="A project skill", body="# Proj")
        agent._pending_skill_draft = draft

        project_dir = tmp_path / "project-skills"

        with patch(
            "basket_assistant.skills.authoring.resolve_project_skills_dir",
            return_value=project_dir,
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.save_pending_skill_draft("project")

        assert "proj-skill" in msg
        assert (project_dir / "proj-skill" / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_clears_pending_after_save(self, mock_coding_agent, tmp_path):
        agent = mock_coding_agent
        agent._pending_skill_draft = SkillDraft(
            name="clear-test", description="Test clearing", body="# Body"
        )

        with patch(
            "basket_assistant.skills.authoring.resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            ctx = agent.build_tool_context()
            await ctx.save_pending_skill_draft("global")

        assert agent._pending_skill_draft is None

    @pytest.mark.asyncio
    async def test_file_exists_returns_error(self, mock_coding_agent, tmp_path):
        agent = mock_coding_agent
        draft = SkillDraft(name="existing-skill", description="Already exists", body="# Body")
        agent._pending_skill_draft = draft

        skill_dir = tmp_path / "existing-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("existing")

        with patch(
            "basket_assistant.skills.authoring.resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.save_pending_skill_draft("global")

        assert msg.startswith("Error:")
        assert "already exists" in msg

    @pytest.mark.asyncio
    async def test_scope_case_insensitive(self, mock_coding_agent, tmp_path):
        agent = mock_coding_agent
        agent._pending_skill_draft = SkillDraft(
            name="case-test", description="Test case", body="# Body"
        )

        with patch(
            "basket_assistant.skills.authoring.resolve_global_skills_dir",
            return_value=tmp_path,
        ):
            ctx = agent.build_tool_context()
            msg = await ctx.save_pending_skill_draft("GLOBAL")

        assert "saved" in msg.lower()


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
