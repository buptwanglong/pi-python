"""
Load subagent configs from .basket/agents/*.md (YAML frontmatter + body).
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .settings import SubAgentConfig

logger = logging.getLogger(__name__)


def _parse_frontmatter_and_body(text: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML-like frontmatter and body. Returns (frontmatter_dict, body)."""
    text = text.strip()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_block = parts[1].strip()
    body = parts[2].strip()

    fm: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_value: List[str] = []

    for line in fm_block.splitlines():
        m = re.match(r"^(\w+)\s*:\s*(.*)$", line)
        if m:
            if current_key:
                fm[current_key] = "\n".join(current_value).strip().strip("'\"").strip()
                current_value = []
            key, rest = m.group(1).lower(), m.group(2).strip().strip("'\"")
            current_key = key
            if rest:
                current_value = [rest]
            else:
                current_value = []
            continue
        if current_key and (line.startswith("  ") or line.startswith("\t")):
            current_value.append(line.strip())
            continue
        if current_key:
            fm[current_key] = "\n".join(current_value).strip().strip("'\"").strip()
            current_key = None
            current_value = []

    if current_key:
        fm[current_key] = "\n".join(current_value).strip().strip("'\"").strip()

    # Parse nested structures for model and tools
    if "model" in fm and isinstance(fm["model"], str):
        model_str = fm["model"]
        model = {}
        for part in model_str.split(","):
            part = part.strip()
            if ":" in part:
                k, v = part.split(":", 1)
                model[k.strip().strip("'\"").lower()] = v.strip().strip("'\"")
        if model:
            fm["model"] = model
        else:
            del fm["model"]
    if "tools" in fm and isinstance(fm["tools"], str):
        tools_str = fm["tools"]
        tools = {}
        for part in tools_str.replace(",", "\n").split():
            if ":" in part:
                k, v = part.split(":", 1)
                v_lower = v.strip().lower()
                tools[k.strip().strip("'\"").lower()] = v_lower in ("true", "1", "yes")
        if tools:
            fm["tools"] = tools
        else:
            del fm["tools"]

    return fm, body


def load_agents_from_dirs(dirs: List[Path]) -> Dict[str, SubAgentConfig]:
    """
    Scan dirs for *.md files; filename stem = agent name.
    Parse frontmatter (description required, prompt/model/tools optional) + body.
    Body is used as prompt when frontmatter has no 'prompt'.
    Later dirs override earlier for same name.
    """
    result: Dict[str, SubAgentConfig] = {}
    for d in dirs:
        expanded = d.expanduser().resolve()
        if not expanded.exists() or not expanded.is_dir():
            continue
        for path in expanded.glob("*.md"):
            if path.name.startswith("_"):
                continue
            name = path.stem
            try:
                raw = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read agent file %s: %s", path, e)
                continue
            fm, body = _parse_frontmatter_and_body(raw)
            description = fm.get("description") or (body.split("\n\n")[0][:200] if body else "(no description)")
            prompt = fm.get("prompt") or body.strip() or ""
            if not prompt:
                logger.warning("Agent %s: missing prompt and empty body, skipping", path)
                continue
            model = fm.get("model") if isinstance(fm.get("model"), dict) else None
            tools = fm.get("tools") if isinstance(fm.get("tools"), dict) else None
            result[name] = SubAgentConfig(
                description=description,
                prompt=prompt,
                model=model,
                tools=tools,
            )
    return result
