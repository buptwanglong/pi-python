"""Tests for /create-skill command."""

import json
from unittest.mock import AsyncMock, patch

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
    extract_conversation_text,
    format_skill_md,
    generate_skill_draft,
    sanitize_skill_name,
)


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
        assert "description: How to deploy with Docker" in result
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
