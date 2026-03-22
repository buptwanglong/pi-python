---
name: create-skill
description: "Turn the current session into a reusable skill (draft, user confirmation, then persist)."
---

# Create skill from session

Use this when the user wants to capture repeatable know-how from the conversation as an OpenCode-style skill.

**Tool definitions** for this workflow live in this skill’s `scripts/skill_authoring_tools.py` (registered at assistant startup). You must invoke the tools by name as below—not by running that file as a standalone script.

## Workflow

1. **Draft** — Call the `draft_skill_from_session` tool (optional `topic_hint` string). It reads the active session messages and uses the model to produce a structured draft. The tool returns a preview (name, description, full SKILL.md body). **Do not** claim the skill is saved yet.
2. **Review** — Present the preview clearly. Wait for the user to confirm or request edits. If they want changes, adjust verbally or re-run draft with a clearer `topic_hint` after more discussion.
3. **Save (final step)** — Only after explicit user confirmation, call `save_pending_skill_draft` with `scope` set to `global` (writes under `~/.basket/skills/<name>/`) or `project` (writes under `./.basket/skills/<name>/`). **Never** call save without clear user consent.

## Rules

- If there is no active session or no usable messages, the draft tool will return an error; explain and stop.
- If a skill with the same name already exists at the target location, the save tool will fail; tell the user and offer to rename or overwrite manually.
- After a successful save, the new skill is discoverable via the normal `skill` tool.
