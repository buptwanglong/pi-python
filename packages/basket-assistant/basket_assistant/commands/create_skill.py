"""
/create-skill command: create a reusable skill from conversation content.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any

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

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# System prompt for LLM-based skill generation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Conversation extraction
# ---------------------------------------------------------------------------


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

    Args:
        messages: Conversation messages (UserMessage, AssistantMessage, etc.).
        max_messages: Maximum number of recent messages to include.
        topic_hint: Optional topic hint to prepend for context.

    Returns:
        A single string with the extracted conversation text, or "" if empty.
    """
    if not messages:
        return ""

    # Take only the last N messages (immutable slice, no mutation)
    truncated = messages[-max_messages:]

    lines: list[str] = []

    if topic_hint:
        lines.append(f"Topic: {topic_hint}")
        lines.append("")

    for msg in truncated:
        if isinstance(msg, UserMessage):
            # content can be str or list of content blocks
            if isinstance(msg.content, str):
                lines.append(f"User: {msg.content}")
            else:
                # List of TextContent / ImageContent blocks
                text_parts = [block.text for block in msg.content if hasattr(block, "text")]
                if text_parts:
                    lines.append(f"User: {' '.join(text_parts)}")
        elif isinstance(msg, AssistantMessage):
            text_parts = [block.text for block in msg.content if isinstance(block, TextContent)]
            if text_parts:
                lines.append(f"Assistant: {' '.join(text_parts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SKILL.md formatting
# ---------------------------------------------------------------------------


def format_skill_md(draft: SkillDraft) -> str:
    """
    Format a SkillDraft as SKILL.md content with YAML frontmatter.

    Args:
        draft: Validated skill draft to format.

    Returns:
        String with YAML frontmatter and Markdown body.
    """
    escaped_description = draft.description.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f"---\n"
        f"name: {draft.name}\n"
        f'description: "{escaped_description}"\n'
        f"---\n\n"
        f"{draft.body}\n"
    )


# ---------------------------------------------------------------------------
# Save skill to disk
# ---------------------------------------------------------------------------


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

    Args:
        draft: Validated skill draft to save.
        scope: Where to save — PROJECT or GLOBAL.
        project_skills_dir: Override for project-scoped skills directory.
            Defaults to ``Path.cwd() / ".basket" / "skills"``.
        global_skills_dir: Override for global-scoped skills directory.
            Defaults to ``Path.home() / ".basket" / "skills"``.
        overwrite: If True, overwrite an existing skill directory.
            If False (default), raise FileExistsError on conflict.

    Returns:
        Path to the created SKILL.md file.

    Raises:
        FileExistsError: If the skill directory already exists and
            *overwrite* is False.
    """
    if scope is SkillScope.PROJECT:
        base_dir = project_skills_dir or (Path.cwd() / ".basket" / "skills")
    else:
        base_dir = global_skills_dir or (Path.home() / ".basket" / "skills")

    skill_dir = base_dir / draft.name
    skill_file = skill_dir / "SKILL.md"

    if skill_dir.exists() and not overwrite:
        raise FileExistsError(
            f"Skill directory already exists: {skill_dir}. " f"Use overwrite=True to replace it."
        )

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(format_skill_md(draft), encoding="utf-8")

    return skill_file


# ---------------------------------------------------------------------------
# LLM-based skill generation
# ---------------------------------------------------------------------------


async def generate_skill_draft(
    model: Model,
    conversation_text: str,
    topic_hint: str | None = None,
) -> SkillDraft:
    """
    Call an LLM to generate a SkillDraft from conversation text.

    The LLM is prompted to return a JSON object with name, description, and body.
    The returned name is sanitized to guarantee it matches the required pattern.

    Args:
        model: Model configuration (passed to ``basket_ai.api.complete``).
        conversation_text: Extracted conversation text to summarize.
        topic_hint: Optional topic hint to include in the prompt.

    Returns:
        A validated SkillDraft.

    Raises:
        ValueError: If the LLM response cannot be parsed as valid JSON
            or is missing required fields.
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

    # Extract text from the first TextContent block
    raw_text = ""
    for block in response.content:
        if isinstance(block, TextContent):
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError("LLM returned no text content")

    # Strip markdown fences if present (```json ... ```)
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence
        lines = stripped.split("\n")
        # Drop first line (```json or ```) and last line (```)
        lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
        stripped = "\n".join(lines)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    # Validate required fields
    for field in ("name", "description", "body"):
        if field not in data:
            raise ValueError(f"LLM response missing required field: {field!r}")

    # Sanitize the name to ensure it matches the pattern
    raw_name = str(data["name"])
    sanitized_name = sanitize_skill_name(raw_name)
    if not sanitized_name:
        raise ValueError(f"Could not sanitize skill name from LLM response: {raw_name!r}")

    return SkillDraft(
        name=sanitized_name,
        description=str(data["description"]),
        body=str(data["body"]),
    )


# ---------------------------------------------------------------------------
# Directory resolution helpers
# ---------------------------------------------------------------------------


def _resolve_global_skills_dir() -> Path:
    """Return the global skills directory path."""
    return Path.home() / ".basket" / "skills"


def _resolve_project_skills_dir() -> Path:
    """Return the project-scoped skills directory path."""
    return Path.cwd() / ".basket" / "skills"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def handle_create_skill(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /create-skill command.

    Generates a skill draft from the current session's conversation history
    and stores it on the agent for subsequent /save-skill usage.

    Args:
        agent: The agent instance with session_manager, _session_id, and model.
        args: Optional topic hint string.

    Returns:
        Tuple of (success, message).
    """
    topic_hint = args.strip() or None

    # Check session availability
    if agent.session_manager is None or agent._session_id is None:
        return False, "No active session. Cannot create skill."

    # Load messages from session
    messages = await agent.session_manager.load_messages(agent._session_id)
    if not messages:
        return False, "Current session has no conversation history. Cannot generate skill."

    # Extract conversation text
    conversation_text = extract_conversation_text(messages, topic_hint=topic_hint)
    if not conversation_text.strip():
        return False, "No usable conversation text found."

    # Generate draft via LLM
    try:
        draft = await generate_skill_draft(agent.model, conversation_text, topic_hint=topic_hint)
    except ValueError as e:
        return False, f"Failed to generate skill draft: {e}"

    # Format preview for display
    preview = format_skill_md(draft)
    preview_display = (
        f"📝 Skill draft generated:\n"
        f"  Name: {draft.name}\n"
        f"  Description: {draft.description}\n"
        f"{'─' * 40}\n"
        f"{preview}\n"
        f"{'─' * 40}\n"
        f"Use '/save-skill project' or '/save-skill global' to save."
    )

    # Store draft on agent for /save-skill
    agent._pending_skill_draft = draft
    return True, preview_display


async def handle_save_skill(agent: Any, args: str) -> tuple[bool, str]:
    """Handle /save-skill command.

    Saves the pending skill draft (from /create-skill) to disk at
    either global or project scope.

    Args:
        agent: The agent instance with _pending_skill_draft attribute.
        args: Scope string — "global" or "project".

    Returns:
        Tuple of (success, message).
    """
    draft = getattr(agent, "_pending_skill_draft", None)
    if draft is None:
        return False, "No pending skill draft. Run /create-skill first."

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

    try:
        saved_path = save_skill_to_disk(
            draft,
            scope,
            project_skills_dir=_resolve_project_skills_dir(),
            global_skills_dir=_resolve_global_skills_dir(),
        )
    except FileExistsError:
        return False, f"Skill '{draft.name}' already exists at target location."
    except OSError as e:
        return False, f"Failed to save skill: {e}"

    agent._pending_skill_draft = None
    return True, (
        f"✅ Skill '{draft.name}' saved to {saved_path.parent}\n"
        f"It is now available via the skill tool."
    )
