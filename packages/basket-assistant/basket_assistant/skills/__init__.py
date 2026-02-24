"""Skills: load skill index and full content for system prompt injection."""

from .loader import get_skill_full_content, get_skills_index

__all__ = ["get_skills_index", "get_skill_full_content"]
