"""
Logic for authoring OpenCode-style skills: draft from conversation (LLM), SKILL.md formatting, disk layout.

Lives under ``basket_assistant.skills`` (with ``registry`` and ``builtin/``), not ``core``, because it is
skill-format-specific. Session binding and ``_pending_skill_draft`` live on ``AssistantAgent`` /
``AgentContext``; this module stays free of agent imports.

Used by ``draft_skill_from_session`` / ``save_pending_skill_draft`` (see builtin create-skill ``scripts/``).
"""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from basket_ai.api import complete
from basket_ai.types import (
    AssistantMessage,
    Context,
    Message,
    Model,
    TextContent,
    UserMessage,
)
from pydantic import BaseModel, Field, field_validator

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
            raise ValueError(f"Skill name must match ^[a-z0-9]+(-[a-z0-9]+)*$, got {v!r}")
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
    result = raw.lower().strip()
    result = re.sub(r"[^a-z0-9-]", "-", result)
    result = re.sub(r"-{2,}", "-", result)
    result = result.strip("-")
    if len(result) > _NAME_MAX_LEN:
        result = result[:_NAME_MAX_LEN].rstrip("-")
    return result


_GENERATION_SYSTEM_PROMPT = (
    "You are a skill generator. "
    "Given a conversation summary, create a reusable skill document.\n\n"
    "Respond with a JSON object (no markdown fences) containing exactly these fields:\n"
    '- "name": lowercase alphanumeric with hyphens only '
    '(e.g. "docker-deploy"), max 64 chars\n'
    '- "description": one-line description of what this skill teaches '
    "(max 200 chars)\n"
    '- "body": Markdown body with sections like ## Overview, ## Steps, ## Examples\n\n'
    "Focus on extracting actionable knowledge, patterns, and step-by-step instructions.\n"
    "Make the skill self-contained so someone can follow it "
    "without the original conversation."
)


def extract_conversation_text(
    messages: list[Message],
    *,
    max_messages: int = 50,
    topic_hint: str | None = None,
) -> str:
    """
    Extract readable text from a list of Message objects.

    Takes the last *max_messages* messages, extracts user and assistant text,
    and optionally prepends a topic hint.
    """
    if not messages:
        return ""

    truncated = messages[-max_messages:]

    lines: list[str] = []

    if topic_hint:
        lines.append(f"Topic: {topic_hint}")
        lines.append("")

    for msg in truncated:
        if isinstance(msg, UserMessage):
            if isinstance(msg.content, str):
                lines.append(f"User: {msg.content}")
            else:
                text_parts = [block.text for block in msg.content if hasattr(block, "text")]
                if text_parts:
                    lines.append(f"User: {' '.join(text_parts)}")
        elif isinstance(msg, AssistantMessage):
            text_parts = [block.text for block in msg.content if isinstance(block, TextContent)]
            if text_parts:
                lines.append(f"Assistant: {' '.join(text_parts)}")

    return "\n".join(lines)


def format_skill_md(draft: SkillDraft) -> str:
    """Format a SkillDraft as SKILL.md content with YAML frontmatter."""
    escaped_description = draft.description.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f"---\n"
        f"name: {draft.name}\n"
        f'description: "{escaped_description}"\n'
        f"---\n\n"
        f"{draft.body}\n"
    )


def save_skill_to_disk(
    draft: SkillDraft,
    scope: SkillScope,
    *,
    project_skills_dir: Path | None = None,
    global_skills_dir: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Write a SkillDraft to disk as a SKILL.md file.

    Raises:
        FileExistsError: If the skill directory already exists and *overwrite* is False.
    """
    if scope is SkillScope.PROJECT:
        base_dir = project_skills_dir or (Path.cwd() / ".basket" / "skills")
    else:
        base_dir = global_skills_dir or (Path.home() / ".basket" / "skills")

    skill_dir = base_dir / draft.name
    skill_file = skill_dir / "SKILL.md"

    if skill_dir.exists() and not overwrite:
        raise FileExistsError(
            f"Skill directory already exists: {skill_dir}. Use overwrite=True to replace it."
        )

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(format_skill_md(draft), encoding="utf-8")

    return skill_file


async def generate_skill_draft(
    model: Model,
    conversation_text: str,
    topic_hint: str | None = None,
) -> SkillDraft:
    """
    Call an LLM to generate a SkillDraft from conversation text.

    Raises:
        ValueError: If the LLM response cannot be parsed or is missing required fields.
    """
    user_prompt_parts = ["Create a skill from this conversation:\n"]
    if topic_hint:
        user_prompt_parts.append(f"Topic hint: {topic_hint}\n")
    user_prompt_parts.append(conversation_text)
    user_prompt = "\n".join(user_prompt_parts)

    context = Context(
        systemPrompt=_GENERATION_SYSTEM_PROMPT,
        messages=[
            UserMessage(role="user", content=user_prompt, timestamp=0),
        ],
    )

    response: AssistantMessage = await complete(model, context)

    raw_text = ""
    for block in response.content:
        if isinstance(block, TextContent):
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError("LLM returned no text content")

    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
        stripped = "\n".join(lines)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    for field in ("name", "description", "body"):
        if field not in data:
            raise ValueError(f"LLM response missing required field: {field!r}")

    raw_name = str(data["name"])
    sanitized_name = sanitize_skill_name(raw_name)
    if not sanitized_name:
        raise ValueError(f"Could not sanitize skill name from LLM response: {raw_name!r}")

    return SkillDraft(
        name=sanitized_name,
        description=str(data["description"]),
        body=str(data["body"]),
    )


def resolve_global_skills_dir() -> Path:
    """Return the global skills directory path."""
    return Path.home() / ".basket" / "skills"


def resolve_project_skills_dir() -> Path:
    """Return the project-scoped skills directory path."""
    return Path.cwd() / ".basket" / "skills"


__all__ = [
    "SkillDraft",
    "SkillScope",
    "extract_conversation_text",
    "format_skill_md",
    "generate_skill_draft",
    "resolve_global_skills_dir",
    "resolve_project_skills_dir",
    "sanitize_skill_name",
    "save_skill_to_disk",
]
