"""从文件系统加载智能体配置（.md 文件或目录）"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SubAgentConfig

logger = logging.getLogger(__name__)

# OpenClaw 风格工作区标记文件
WORKSPACE_MARKER_FILES = ("AGENTS.md", "IDENTITY.md")


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


class AgentLoader:
    """从文件系统加载智能体配置"""

    @staticmethod
    def load_from_dirs(dirs: List[Path]) -> Dict[str, SubAgentConfig]:
        """
        从目录列表扫描并加载智能体

        支持两种格式：
        1. 目录型：包含 AGENTS.md 或 IDENTITY.md 的子目录
        2. 单文件型：*.md 文件，带 YAML frontmatter

        优先级：后面的目录覆盖前面的；同名时目录型优先于单文件型
        """
        result: Dict[str, SubAgentConfig] = {}
        for d in dirs:
            expanded = d.expanduser().resolve()
            if not expanded.exists() or not expanded.is_dir():
                continue
            # 1) Directory-type agents (OpenClaw-style workspace per agent) in this dir only
            # Prefer subdir/workspace/ when present (md files + memory there); else subdir as workspace
            dir_agent_names: set = set()
            for subdir in expanded.iterdir():
                if not subdir.is_dir() or subdir.name.startswith("_"):
                    continue
                workspace_sub = subdir / "workspace"
                if workspace_sub.exists() and workspace_sub.is_dir() and any(
                    (workspace_sub / f).exists() and (workspace_sub / f).is_file() for f in WORKSPACE_MARKER_FILES
                ):
                    ws_dir = workspace_sub
                elif any((subdir / f).exists() and (subdir / f).is_file() for f in WORKSPACE_MARKER_FILES):
                    ws_dir = subdir
                else:
                    continue
                name = subdir.name
                dir_agent_names.add(name)
                result[name] = SubAgentConfig(
                    model=None,
                    tools=None,
                    agent_dir=str(subdir.resolve()),
                    workspace_dir=str(ws_dir.resolve()),
                )
            # 2) Single-file agents (*.md); skip only if same name from directory in this dir (directory wins)
            for path in expanded.glob("*.md"):
                if path.name.startswith("_"):
                    continue
                name = path.stem
                if name in dir_agent_names:
                    continue
                try:
                    raw = path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("Failed to read agent file %s: %s", path, e)
                    continue
                fm, body = _parse_frontmatter_and_body(raw)
                model = fm.get("model") if isinstance(fm.get("model"), dict) else None
                tools = fm.get("tools") if isinstance(fm.get("tools"), dict) else None
                workspace_dir_from_fm = fm.get("workspace_dir")
                if isinstance(workspace_dir_from_fm, str) and workspace_dir_from_fm.strip():
                    workspace_dir_val: Optional[str] = workspace_dir_from_fm.strip()
                else:
                    workspace_dir_val = None
                result[name] = SubAgentConfig(
                    model=model,
                    tools=tools,
                    workspace_dir=workspace_dir_val,
                )
        return result
