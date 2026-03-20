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
