# Basket Extensibility Gap Analysis: Command / Skill / Extension

**Date:** 2026-03-21
**Reference Standards:** Claude Code + OpenClaw
**Scope:** Command system, Skill system, Extension/Plugin/Hook system

---

## 1. Concept Mapping

Three-way mapping of extensibility concepts across Claude Code, OpenClaw, and Basket:

| Concept | Claude Code | OpenClaw | Basket (Current) |
|---------|-------------|----------|-------------------|
| **Built-in commands** | Slash Commands (`/help`, `/clear`, `/compact`, `/init`, `/model`, etc.) | Slash Commands (similar) | Commands (`/help`, `/settings`, `/sessions`, `/open`, `/plan`, `/todos`, `/create-skill`, `/save-skill`) |
| **Knowledge injection** | Skills (SKILL.md, `Skill` tool) | Skills (SKILL.md, same format) | Skills (SKILL.md, `skill` tool) — **aligned** |
| **Tool execution interception** | Hooks (`PreToolUse`, `PostToolUse`, `Stop` in settings.json) | Similar mechanism | Hooks (`tool.execute.before/after`, `.basket/hooks.json`) + Extension events |
| **External tool extension** | MCP Servers (stdio/sse) | MCP Servers | **Missing** — no MCP support |
| **Custom agents** | Custom Agents (`.claude/agents/*.md`) | Similar | SubAgents (settings.json config) |
| **Project instructions** | CLAUDE.md (global + project) | Similar | **Missing** — system prompt is hardcoded |
| **Packaging & distribution** | Plugins (agents + skills + hooks + rules) | N/A | Extensions (`.py` modules, no packaging) |

**Key finding:** Basket's Extension system is a merged concept combining Claude Code's Hooks + MCP-like tool registration + Commands into a single Python module mechanism.

---

## 2. Command System Gap Analysis

### 2.1 Current State

- **8 built-in commands:** `/help`, `/settings`, `/todos`, `/plan`, `/sessions`, `/open`, `/create-skill`, `/save-skill`
- **Special handling:** `/exit`, `/quit` (hardcoded), `/skill <id>` (priority-3 routing)
- **Registration:** `CommandRegistry` + `register_command()` decorator (Extensions can add commands)
- **Routing:** 5-level priority `InputProcessor`

### 2.2 Command-by-Command Comparison

| Claude Code | Purpose | Basket Equivalent | Gap Level |
|-------------|---------|-------------------|-----------|
| `/help` | Show help | `/help` | — |
| `/clear` | Clear context | **Missing** | **P0** |
| `/compact` | Compress context | **Missing** | **P0** |
| `/init` | Initialize CLAUDE.md | **Missing** (CLI `basket init` only manages settings) | **P1** |
| `/model` | Switch model at runtime | **Missing** | **P1** |
| `/cost` | Token/cost tracking | **Missing** | P2 |
| `/review` | Code review | **Missing** | P3 |
| `/commit` | Git commit | **Missing** | P3 |
| `/pr` | Create PR | **Missing** | P3 |
| `/config` | View/modify config | `/settings` (read-only) | P2 |
| `/skill` | Load skill | `/skill <id>` | — |
| `/login` | Auth management | **Missing** | P3 |
| `/permissions` | Permission management | **Missing** | P3 |
| `/memory` | Edit CLAUDE.md | **Missing** | **P1** |
| `/status` | Health check | **Missing** | P3 |
| `/sessions` | Session management | `/sessions` + `/open` | — |
| `/plan` | Plan mode | `/plan` | — |
| `/todos` | Todo display | `/todos` | — |

### 2.3 Command System Gap Summary

| Priority | Gap | Description |
|----------|-----|-------------|
| **P0** | `/clear` | Cannot reset conversation context; must restart process for long conversations |
| **P0** | `/compact` | No context compression; no solution when context window overflows |
| **P1** | `/model` | Cannot switch model at runtime; must restart |
| **P1** | `/memory` + `/init` | No project instruction file (CLAUDE.md equivalent) + no runtime editing |
| P2 | `/cost` | Missing token usage and cost tracking |
| P2 | `/config` writable | `/settings` is read-only; cannot modify config at runtime |
| P3 | `/review`, `/commit`, `/pr` | Dev workflow commands (can be partially replaced by Skills) |

---

## 3. Skill System Gap Analysis

### 3.1 Current State — Highly Aligned

The Skill system is the **best-aligned** of the three systems:

| Dimension | Claude Code | Basket | Status |
|-----------|-------------|--------|--------|
| **Format** | SKILL.md + YAML frontmatter | SKILL.md + YAML frontmatter | Aligned |
| **Fields** | `name`, `description` | `name`, `description` | Aligned |
| **Naming rules** | `^[a-z0-9]+(-[a-z0-9]+)*$` | `^[a-z0-9]+(-[a-z0-9]+)*$` | Aligned |
| **Directory discovery** | `~/.claude/skills/`, `.claude/skills/` | 8 search paths (includes `~/.claude/skills/`) | Superset |
| **Invocation** | `Skill` tool (LLM auto-invocation) | `skill` tool (LLM auto-invocation) | Aligned |
| **Interactive invocation** | `/skill <id> [message]` | `/skill <id>` | Gap: missing message parameter |
| **Sub-directories** | No standard | `scripts/`, `references/`, `assets/` | Basket advantage |
| **Creation workflow** | No built-in | `/create-skill` + `/save-skill` | Basket advantage |
| **Filtering** | None | `skills_include` whitelist | Basket advantage |

### 3.2 Skill System Gaps

| Priority | Gap | Description |
|----------|-----|-------------|
| P2 | `/skill <id> [message]` | Claude Code supports attaching a message when invoking a skill; Basket only passes skill id |
| P2 | Skill parameterization | Claude Code Skills can have `input_schema` for structured input parameters (via YAML frontmatter `arguments`); Basket lacks this |
| P3 | Skill provenance tracking | Claude Code Plugin system tracks which plugin provides each skill; Basket has no such metadata |
| P3 | Skill hot-reload | Neither supports it, but valuable for development experience |

### 3.3 Basket Unique Advantages (Preserve)

- **`scripts/` and `references/` sub-directories:** Skills can bundle executable scripts and reference docs — Claude Code has no equivalent
- **`/create-skill` + `/save-skill`:** Extract skills from conversation automatically — Claude Code has no built-in equivalent
- **`skills_include` filtering:** Restrict available skills per agent
- **`init_skill.py` scaffolding:** CLI template generation for new skills

---

## 4. Extension / Plugin / Hook System Gap Analysis

This is the area with the **largest gap** and most significant architectural differences.

### 4.1 Architectural Comparison

**Claude Code** separates extensibility into 3 independent, orthogonal mechanisms:

```
Claude Code:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     Hooks        │  │   MCP Servers   │  │    Plugins      │
│                  │  │                 │  │                 │
│ • PreToolUse     │  │ • stdio/sse     │  │ • agents/       │
│ • PostToolUse    │  │ • Tool provider │  │ • skills/       │
│ • Stop           │  │ • Resource      │  │ • hooks/        │
│ • Notification   │  │ • Protocol std  │  │ • rules/        │
│                  │  │                 │  │ • Installable   │
│ Intercept/audit  │  │ Add ext. tools  │  │ Package/distrib │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Basket** combines these capabilities into a single Extension system:

```
Basket:
┌──────────────────────────────────────────────┐
│              Extension (.py module)           │
│                                              │
│  setup(basket: ExtensionAPI):                │
│    • @register_tool()     ← MCP-like        │
│    • @register_command()  ← Slash command    │
│    • @on("event")         ← Hook-like       │
│                                              │
│  + Subprocess Hooks (.basket/hooks.json)     │
│    • tool.execute.before/after               │
│    • session.created                         │
│    • message.turn_done                       │
└──────────────────────────────────────────────┘
```

### 4.2 Hooks Comparison

| Dimension | Claude Code | Basket |
|-----------|-------------|--------|
| **Config location** | `~/.claude/settings.json` → `hooks` | `.basket/hooks.json` or `~/.basket/hooks.json` |
| **Hook types** | `PreToolUse`, `PostToolUse`, `Stop`, `Notification` | `tool.execute.before`, `tool.execute.after`, `session.created`, `message.turn_done` |
| **Matching** | Hook name = tool name or `*` wildcard | `matcher` regex filter |
| **Execution** | Subprocess (bash/python/etc.) | Subprocess (bash/python/etc.) — aligned |
| **Communication** | stdin JSON → stdout JSON | stdin JSON → stdout JSON — aligned |
| **Blocking** | `exit 2` blocks execution | `exit 2` or `"permission": "deny"` — aligned |
| **Parameter modification** | Can modify tool params via stdout | Unconfirmed support |
| **Multi-hook chaining** | Multiple hooks per event | Supported |

**Hooks Gaps:**

| Priority | Gap | Description |
|----------|-----|-------------|
| **P1** | Hook type naming inconsistency | `PreToolUse` vs `tool.execute.before` — same semantics, different names |
| P2 | Missing `Stop` Hook | Claude Code can trigger validation when session ends |
| P2 | Missing `Notification` Hook | Claude Code can send notifications on specific events |
| P2 | Hook config location difference | Claude Code uses settings.json; Basket uses separate hooks.json |
| P3 | Missing tool parameter modification | Claude Code hooks can modify tool call parameters |

### 4.3 Extension vs MCP + Plugin Comparison

| Dimension | Claude Code MCP | Claude Code Plugin | Basket Extension |
|-----------|----------------|-------------------|-----------------|
| **Nature** | External process providing tools | Packaging/distribution unit | Python module registering everything |
| **Language** | Any (stdio/sse) | N/A (contains multiple file types) | Python only |
| **Add tools** | Standard MCP protocol | Contains MCP config | `@register_tool()` |
| **Add commands** | No | Contains skills | `@register_command()` |
| **Event listeners** | No | Contains hooks | `@on("event")` |
| **Discovery** | `settings.json` → `mcpServers` | `~/.claude/plugins/` | `~/.basket/extensions/` + `./extensions/` |
| **Isolation** | Process isolation | Directory isolation | In-process (no isolation) |
| **Install management** | Manual config | `claude plugin add/remove` | Manual file placement |
| **Ecosystem interop** | Standard protocol (universal) | Claude Code specific | Basket specific |

**Extension System Gaps:**

| Priority | Gap | Description |
|----------|-----|-------------|
| **P0** | No MCP Server support | Claude Code's core extension mechanism; ecosystem barrier. Basket cannot use any MCP tools (GitHub, Sentry, database MCP servers all unavailable) |
| **P1** | No Plugin packaging | Basket Extensions are loose `.py` files; no versioning, no install/uninstall commands |
| **P1** | Extensions Python-only | Claude Code Hooks/MCP are language-agnostic; Basket Extensions must be Python |
| P2 | No Extension lifecycle management | No teardown/unload; no enable/disable toggle |
| P2 | No Extension isolation | In-process execution; one crashing Extension can affect the entire agent |
| P3 | Extension directory convention mismatch | Claude Code uses `.claude/` prefix; Basket uses `.basket/` + `~/.basket/` |

### 4.4 Recommended Architecture Redesign

Separate current Extension's responsibilities into 4 orthogonal mechanisms:

```
Recommended Architecture:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    Hooks     │  │     MCP      │  │  Extensions  │  │   Plugins    │
│              │  │   Servers    │  │  (simplified) │  │  (new)       │
│ PreToolUse   │  │ stdio/sse    │  │ Python-only  │  │ = skills +   │
│ PostToolUse  │  │ Standard     │  │ events/cmds  │  │   hooks +    │
│ Stop         │  │ protocol     │  │ internal     │  │   agents +   │
│ Notification │  │ Add external │  │ enhancement  │  │   rules      │
│              │  │ tools        │  │              │  │              │
│ Intercept/   │  │ Tool         │  │ Internal     │  │ Package/     │
│ audit        │  │ extension    │  │ extension    │  │ distribution │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 5. Global Gap Summary — Priority Ranking

### 5.1 Critical (P0) — Missing Functionality

| # | Gap | System | Impact | Recommendation |
|---|-----|--------|--------|----------------|
| 1 | **No MCP Server support** | Extension | Cannot access MCP ecosystem (GitHub, Sentry, DB, etc. — dozens of ready-made MCP servers unavailable); largest ecosystem barrier | Implement MCP Client (stdio + sse); align config with Claude Code `mcpServers` format in settings.json |
| 2 | **No `/clear` command** | Command | Cannot reset context in long conversations; must restart process | Implement `/clear`: clear conversation history, preserve system prompt |
| 3 | **No `/compact` command** | Command | No solution when context window overflows in long sessions | Implement `/compact`: LLM auto-summarizes history, compresses to summary |

### 5.2 Major (P1) — Behavioral Differences

| # | Gap | System | Recommendation |
|---|-----|--------|----------------|
| 4 | No `/model` runtime switch | Command | Implement `/model [provider/model]` for runtime switching |
| 5 | No project instruction file system | Cross-system | Implement CLAUDE.md / BASKET.md equivalent + `/memory` edit command |
| 6 | Hook type naming inconsistency | Hook | Unify to `PreToolUse`/`PostToolUse`/`Stop` or provide aliases |
| 7 | No Plugin packaging/distribution | Extension | Design Plugin format (directory containing skills/ + hooks/ + agents/ + rules/) |
| 8 | Extensions Python-only | Extension | Short-term: maintain; long-term: cross-language tool extension via MCP |

### 5.3 Minor (P2–P3)

| # | Gap | System | Priority |
|---|-----|--------|----------|
| 9 | `/cost` token/cost tracking | Command | P2 |
| 10 | `/settings` writable | Command | P2 |
| 11 | Missing `Stop` / `Notification` Hook types | Hook | P2 |
| 12 | Hook config location → unify into settings | Hook | P2 |
| 13 | Extension no teardown / enable-disable | Extension | P2 |
| 14 | `/skill <id> [message]` message parameter support | Skill | P2 |
| 15 | Skill parameterization (input_schema) | Skill | P2 |
| 16 | Extension process isolation | Extension | P3 |
| 17 | `/review`, `/commit`, `/pr` workflow commands | Command | P3 |

### 5.4 Basket Unique Advantages (Preserve)

| Advantage | System | Description |
|-----------|--------|-------------|
| Skill `scripts/` + `references/` sub-dirs | Skill | Skills can bundle executable scripts and reference docs; Claude Code lacks this |
| `/create-skill` + `/save-skill` | Skill | Auto-extract skills from conversation; Claude Code has no built-in equivalent |
| `skills_include` filtering | Skill | Restrict agent's available skills |
| Extension four-in-one | Extension | Single .py registers tools + commands + events; concise developer experience |
| 5-level priority routing | Command | InputProcessor's multi-level routing is more granular than Claude Code |
| SubAgent declarative config | Cross-system | settings.json declarative sub-agent configuration; high flexibility |

---

## 6. Recommended Implementation Roadmap

```
Phase 1 (P0): MCP Client + /clear + /compact
  └─ Unblocks ecosystem access and long-session usability
  ↓
Phase 2 (P1): /model + Project instruction files + Hook naming unification
  └─ Runtime flexibility and developer experience alignment
  ↓
Phase 3 (P1): Plugin packaging format design
  └─ Enables sharing and distribution of extensions
  ↓
Phase 4 (P2): /cost + Stop Hook + Extension lifecycle
  └─ Observability and robustness improvements
  ↓
Phase 5 (P2–P3): Skill enhancements + Workflow commands
  └─ Feature completeness and developer productivity
```

---

## Appendix: File References

| Component | Key Files |
|-----------|-----------|
| Command Registry | `packages/basket-assistant/basket_assistant/interaction/commands/registry.py` |
| Command Handlers | `packages/basket-assistant/basket_assistant/interaction/commands/handlers.py` |
| Input Processor | `packages/basket-assistant/basket_assistant/interaction/processors/input_processor.py` |
| Skill Loader | `packages/basket-assistant/basket_assistant/core/skills_loader.py` |
| Skill Tool | `packages/basket-assistant/basket_assistant/tools/skill.py` |
| Skill Creation | `packages/basket-assistant/basket_assistant/commands/create_skill.py` |
| Extension API | `packages/basket-assistant/basket_assistant/extensions/api.py` |
| Extension Loader | `packages/basket-assistant/basket_assistant/extensions/loader.py` |
| Hook Runner | `packages/basket-assistant/basket_assistant/extensions/hook_runner.py` |
| Settings Schema | `packages/basket-assistant/basket_assistant/core/settings_full.py` |
| Agent Tools | `packages/basket-assistant/basket_assistant/agent/tools.py` |
| Agent Prompts | `packages/basket-assistant/basket_assistant/agent/prompts.py` |
