"""
/create-skill command: create a reusable skill from conversation content.
"""

import re
from enum import Enum

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
