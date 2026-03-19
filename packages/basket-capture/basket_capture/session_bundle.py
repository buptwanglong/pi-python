"""Session bundle layout: session.cast, input.jsonl, actions/*/meta.json, session_manifest.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Default action boundary: Ctrl+\ → raw TTY byte 0x1C (ASCII FS)
DEFAULT_ACTION_BOUNDARY_BYTE = 0x1C

_SCHEMA_VERSION = 1


def slugify_label(text: str, max_len: int = 32) -> str:
    """Lowercase slug: alnum and hyphen only; collapse others to hyphen."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        return "segment"
    return s[:max_len]


def new_session_dir(sessions_parent: Path, *, now: datetime | None = None) -> Path:
    """Create ~/.basket/capture/sessions/session-YYYYMMDD-HHMMSS/ and return it."""
    dt = now or datetime.now()
    ts = dt.strftime("%Y%m%d-%H%M%S")
    session_id = f"session-{ts}"
    root = sessions_parent / session_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "actions").mkdir(exist_ok=True)
    return root


def default_sessions_parent(home: Path | None = None) -> Path:
    base = Path.home() if home is None else home
    return base / ".basket" / "capture" / "sessions"


@dataclass
class ActionRecord:
    """One closed action segment (for manifest)."""

    dir_relative: str
    t_start_s: float
    t_end_s: float


@dataclass
class SessionBundleWriter:
    """Creates layout and writes meta/manifest; caller appends input.jsonl lines."""

    root: Path
    session_id: str
    started_at_unix: float
    input_lines: list[dict[str, Any]] = field(default_factory=list)
    actions: list[ActionRecord] = field(default_factory=list)
    _input_fp: Any = None

    @property
    def cast_path(self) -> Path:
        return self.root / "session.cast"

    @property
    def input_path(self) -> Path:
        return self.root / "input.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.root / "session_manifest.json"

    def open_input_log(self) -> None:
        self._input_fp = self.input_path.open("w", encoding="utf-8")

    def close_input_log(self) -> None:
        if self._input_fp is not None:
            self._input_fp.close()
            self._input_fp = None

    def append_input_event(self, event: dict[str, Any]) -> None:
        self.input_lines.append(event)
        if self._input_fp is not None:
            self._input_fp.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._input_fp.flush()

    def action_subdirectory(self, seq: int, slug: str) -> Path:
        name = f"{seq:03d}_{slugify_label(slug)}"
        return self.root / "actions" / name

    def ensure_action_dir(self, seq: int, slug: str) -> Path:
        d = self.action_subdirectory(seq, slug)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_action_meta(
        self,
        action_dir: Path,
        *,
        seq: int,
        slug: str,
        t_start_s: float,
        t_end_s: float,
        screenshots: list[str],
    ) -> None:
        rel_screens = [str(Path(s).as_posix()) for s in screenshots]
        meta = {
            "seq": seq,
            "slug": slugify_label(slug),
            "t_start_s": round(t_start_s, 6),
            "t_end_s": round(t_end_s, 6),
            "screenshots": rel_screens,
        }
        (action_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def register_action(self, rec: ActionRecord) -> None:
        self.actions.append(rec)

    def write_manifest(self, ended_at_unix: float) -> None:
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "session_id": self.session_id,
            "started_at_unix": round(self.started_at_unix, 6),
            "ended_at_unix": round(ended_at_unix, 6),
            "cast_file": "session.cast",
            "input_log": "input.jsonl",
            "actions": [
                {
                    "dir": a.dir_relative,
                    "t_start_s": a.t_start_s,
                    "t_end_s": a.t_end_s,
                }
                for a in self.actions
            ],
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def create_session_bundle(
    sessions_parent: Path,
    *,
    now: datetime | None = None,
    started_at_unix: float | None = None,
) -> SessionBundleWriter:
    """Create a new session directory and return a writer (input log not opened yet)."""
    import time as time_mod

    root = new_session_dir(sessions_parent, now=now)
    session_id = root.name
    start = started_at_unix if started_at_unix is not None else time_mod.time()
    return SessionBundleWriter(root=root, session_id=session_id, started_at_unix=start)
