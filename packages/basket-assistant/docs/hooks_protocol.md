# Hooks protocol (stdin / stdout JSON)

Hooks run as subprocesses. The runner writes one line of JSON to stdin and reads one line of JSON from stdout. Exit code `2` means deny.

## Common input fields (all events)

Every hook receives at least:

| Field | Type | Description |
|-------|------|-------------|
| `hook_event_name` | string | Event name (e.g. `tool.execute.before`, `session.created`) |
| `cwd` | string | Working directory (project root) |
| `workspace_roots` | string[] | List of workspace roots (usually one) |

## tool.execute.before

**When:** Before a tool is executed.

**Input:**

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | string | e.g. `read`, `bash`, `write` |
| `tool_call_id` | string | Id of the tool call |
| `arguments` | object | Tool arguments (e.g. `filePath`, `command`) |
| `cwd` | string | Working directory |

**Output (stdout, one line JSON):**

| Field | Type | Description |
|-------|------|-------------|
| `permission` | `"allow"` \| `"deny"` \| `"ask"` | Allow or deny execution |
| `reason` | string | Shown to agent when denied |
| `modified_arguments` | object | If allow but args should change, new arguments to use |

**Exit code:** `0` = use output; `2` = deny (tool is not run, agent sees an error).

## tool.execute.after

**When:** After a tool has been executed (success or failure).

**Input:**

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | string | Tool that was run |
| `tool_call_id` | string | Id of the tool call |
| `arguments` | object | Arguments that were used |
| `result` | any | Tool return value (or null if error) |
| `error` | string \| null | Error message if tool raised |
| `cwd` | string | Working directory |

**Output:** Optional; no fields required. Hook is for observation/audit.

## session.created

**When:** After a session is set and history/todos have been loaded.

**Input:**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Current session id |
| `directory` | string | Project/working directory |
| `workspace_roots` | string[] | Workspace roots |

**Output:** Optional; no fields required.

## Example script (bash): block reading .env

```bash
#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('arguments',{}).get('filePath','') or d.get('arguments',{}).get('path',''))")
if echo "$file_path" | grep -q '\.env'; then
  echo '{"permission":"deny","reason":"Reading .env files is not allowed."}'
  exit 2
fi
echo '{"permission":"allow"}'
exit 0
```

## Example script (Python): allow and modify

```python
#!/usr/bin/env python3
import json, sys
d = json.load(sys.stdin)
args = d.get("arguments") or {}
if d.get("tool_name") == "bash" and "rm -rf" in args.get("command", ""):
    print(json.dumps({"permission": "deny", "reason": "Blocked dangerous rm -rf."}))
    sys.exit(2)
print(json.dumps({"permission": "allow"}))
sys.exit(0)
```
