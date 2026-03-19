"""Tests for basket_capture.session_bundle."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from basket_capture.session_bundle import (
    ActionRecord,
    SessionBundleWriter,
    create_session_bundle,
    default_sessions_parent,
    new_session_dir,
    slugify_label,
)


def test_slugify_label_basic() -> None:
    assert slugify_label("Open Menu!") == "open-menu"
    assert slugify_label("   ") == "segment"


def test_slugify_label_cjk_becomes_segment() -> None:
    assert slugify_label("你好") == "segment"


def test_default_sessions_parent(tmp_path: Path) -> None:
    p = default_sessions_parent(tmp_path)
    assert p == tmp_path / ".basket" / "capture" / "sessions"


def test_new_session_dir_creates_layout(tmp_path: Path) -> None:
    fixed = datetime(2026, 3, 19, 15, 30, 45)
    root = new_session_dir(tmp_path, now=fixed)
    assert root.name == "session-20260319-153045"
    assert (root / "actions").is_dir()


def test_create_session_bundle(tmp_path: Path) -> None:
    b = create_session_bundle(tmp_path, now=datetime(2026, 1, 2, 3, 4, 5))
    assert b.session_id == "session-20260102-030405"
    assert b.root.parent == tmp_path
    assert (b.root / "actions").is_dir()


def test_session_bundle_writer_manifest(tmp_path: Path) -> None:
    root = new_session_dir(tmp_path)
    w = SessionBundleWriter(root=root, session_id=root.name, started_at_unix=1000.0)
    w.open_input_log()
    w.append_input_event({"t": 0.0, "type": "text", "text": "ab"})
    w.close_input_log()

    adir = w.ensure_action_dir(1, "hello")
    w.write_action_meta(
        adir,
        seq=1,
        slug="hello",
        t_start_s=0.0,
        t_end_s=1.5,
        screenshots=["screenshots/end.png"],
    )
    rel = str(adir.relative_to(w.root)).replace("\\", "/")
    w.register_action(ActionRecord(dir_relative=rel, t_start_s=0.0, t_end_s=1.5))
    w.write_manifest(1002.0)

    manifest = json.loads(w.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["session_id"] == root.name
    assert manifest["cast_file"] == "session.cast"
    assert manifest["input_log"] == "input.jsonl"
    assert len(manifest["actions"]) == 1
    assert manifest["actions"][0]["dir"] == rel

    lines = w.input_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["type"] == "text"

    meta = json.loads((adir / "meta.json").read_text(encoding="utf-8"))
    assert meta["seq"] == 1
    assert meta["slug"] == "hello"
    assert meta["screenshots"] == ["screenshots/end.png"]
