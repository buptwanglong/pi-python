# Design: /create-skill Command

**Date:** 2026-03-20
**Status:** Approved
**Package:** basket-assistant

## Overview

Add a `/create-skill` command to basket-assistant that lets users create reusable skills from conversation content. AI analyzes the current session dialogue, generates a SKILL.md draft, and after user confirmation saves it to the chosen scope (project or global). The skill is immediately available without restarting.

## User Interaction Flow

```
User: /create-skill [optional topic hint]

Step 1: AI analyzes current session dialogue history
  - If topic hint provided, focus on that topic
  - Otherwise, auto-detect key knowledge/patterns/solutions

Step 2: Generate draft and preview
  - Generate SKILL.md content (YAML frontmatter + Markdown body)
  - Display preview in terminal

Step 3: User confirms
  - [1] Save (confirm content)
  - [2] Modify (tell AI what to change, regenerate)
  - [3] Cancel

Step 4: Choose scope
  - [1] Project-level (./.basket/skills/)
  - [2] Global-level (~/.basket/skills/)

Step 5: Write and enable
  - Create skills/<name>/SKILL.md
  - Refresh skills index
  - Output: "Skill '<name>' created and enabled"
```

## Technical Architecture

### New Files

```
packages/basket-assistant/
  basket_assistant/
    commands/
      create_skill.py     # ~200 lines: /create-skill command implementation
  basket_assistant/
    skills/
      skills_loader.py    # Modified: add refresh_skills() method
```

### Core Module: create_skill.py

```python
# Responsibilities

1. register_create_skill_command(basket)
   # Register /create-skill command on the basket instance

2. async extract_conversation_summary(session_messages, topic_hint=None) -> str
   # Extract key knowledge/patterns from dialogue history
   # Input: session message list + optional topic hint
   # Output: structured knowledge summary text

3. async generate_skill_draft(basket, summary, topic_hint=None) -> SkillDraft
   # Call LLM to generate SKILL.md draft
   # Return SkillDraft(name, description, body)

4. async confirm_and_save(basket, draft, scope) -> Path
   # Write SKILL.md file to target directory
   # Refresh skills index
   # Return saved path
```

### Data Models

```python
class SkillDraft(BaseModel):
    name: str          # Must match ^[a-z0-9]+(-[a-z0-9]+)*$
    description: str   # Short description
    body: str          # Markdown body content

class SkillScope(str, Enum):
    PROJECT = "project"   # ./.basket/skills/
    GLOBAL = "global"     # ~/.basket/skills/
```

### Key Implementation Details

**1. Conversation history retrieval:**
- Use `session_manager.load_session(session_id)` to get current session JSONL messages
- Filter `role=user` and `role=assistant` messages
- Truncate to most recent 50 messages to avoid exceeding context window

**2. SKILL.md generation:**
- Use current basket's LLM instance via `complete()`
- System prompt guides AI to produce valid SKILL.md format
- Includes YAML frontmatter (name, description) + Markdown body

**3. Hot-reload / index refresh:**
- After writing file, call `skills_loader.index_skills()` to rescan
- Update agent's system prompt `<available_skills>` list
- Immediately available in current session without restart

**4. Name conflict handling:**
- Check target directory for existing skill with same name before saving
- Prompt user to choose overwrite or rename if conflict exists

## Error Handling

| Scenario | Handling |
|----------|----------|
| Empty session (no dialogue) | Message: "Current dialogue is empty, cannot generate skill" |
| Generated name violates naming rules | Auto-fix: lowercase, replace illegal chars with `-` |
| Target directory does not exist | Auto-create `skills/<name>/` |
| Same-name skill already exists | Prompt user: overwrite or rename |
| LLM call fails | Display error, suggest retry |
| Skills index refresh fails | File saved successfully, prompt user to restart |
| Dialogue history too long | Truncate to most recent 50 messages + use topic_hint to focus |

## Testing Strategy

```
tests/
  test_create_skill_command.py     # Integration tests
    test_create_skill_basic        # Basic creation flow
    test_create_skill_with_hint    # With topic hint
    test_create_skill_conflict     # Name conflict handling
    test_create_skill_empty        # Empty dialogue handling
  test_skill_draft.py              # Unit tests
    test_draft_model_validation    # SkillDraft model validation
    test_name_sanitization         # Name auto-correction
    test_skill_md_generation       # SKILL.md format correctness
  test_skill_scope.py              # Scope tests
    test_project_scope_path        # Project-level path correct
    test_global_scope_path         # Global-level path correct
```

- Mock LLM responses, no real API dependency
- Use `tmp_path` fixture for filesystem isolation
- Verify generated SKILL.md conforms to frontmatter format
- Target coverage: 80%+

## Design Decisions

1. **Command vs Tool**: Chose command (`/create-skill`) because this is a user-initiated action, not something the agent calls autonomously. Commands are designed for this use case.

2. **Save-then-enable**: Writing to a skills_dirs path and refreshing the index means the skill is immediately available. No separate "enable" step needed.

3. **Scope selection at save time**: Rather than a global config, let users decide per-skill whether it should be project-scoped or globally available.

4. **AI generation + user confirmation**: Balances convenience (AI does the heavy lifting) with control (user reviews before saving).
