# Scripts

## skill_authoring_tools.py

Defines and registers the assistant tools used by this skill:

- `draft_skill_from_session` — build a skill draft from the current session (see `SKILL.md`).
- `save_pending_skill_draft` — persist the pending draft after user confirmation.

The basket assistant loads this module at startup via `basket_assistant.skills.registry.load_builtin_skill_tool_modules()` (importlib), because the parent directory is named `create-skill` (hyphen) and is not a Python package.

Persistence and LLM draft formatting live in `basket_assistant.skills.authoring`; callbacks on `AgentContext` perform session I/O and `_pending_skill_draft` handling.
