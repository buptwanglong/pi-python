"""Tests for basket init guided setup (init_guided.run_init_guided)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from basket_assistant.init_guided import run_init_guided


def test_run_init_guided_force_creates_file_with_full_schema(tmp_path):
    """run_init_guided with force=True and piped answers writes valid settings.json."""
    path = tmp_path / "settings.json"
    with patch("builtins.input", side_effect=[
        "1",           # provider openai
        "",            # api key empty
        "",            # model default
        "",            # base_url skip
        "",            # workspace skip
        "1",           # web search duckduckgo
    ]):
        exit_code = run_init_guided(settings_path=path, force=True)
    assert exit_code == 0
    assert path.exists()
    data = json.loads(path.read_text())
    assert "model" in data
    assert data["model"]["provider"] == "openai"
    assert data["model"]["model_id"] == "gpt-4o-mini"
    assert "agent" in data
    assert "api_keys" in data
    assert "agents" in data
    assert data["agents"] == {}
    assert data.get("web_search_provider") is None


def test_run_init_guided_existing_file_no_force_abort(tmp_path):
    """When file exists and force=False, answering N aborts and returns 1."""
    path = tmp_path / "settings.json"
    path.write_text("{}")
    with patch("builtins.input", return_value="n"):
        exit_code = run_init_guided(settings_path=path, force=False)
    assert exit_code == 1
    assert path.read_text() == "{}"


def test_run_init_guided_existing_file_force_overwrites(tmp_path):
    """When file exists and force=True, overwrites without prompting."""
    path = tmp_path / "settings.json"
    path.write_text('{"old": true}')
    with patch("builtins.input", side_effect=["1", "", "", "", "", "1"]):
        exit_code = run_init_guided(settings_path=path, force=True)
    assert exit_code == 0
    data = json.loads(path.read_text())
    assert "model" in data
    assert "old" not in data


def test_run_init_guided_serper_asks_key(tmp_path):
    """Choosing serper adds web_search_provider and optional SERPER_API_KEY."""
    path = tmp_path / "settings.json"
    with patch("builtins.input", side_effect=[
        "1", "", "", "", "", "2", "sk-serper-test",
    ]):
        exit_code = run_init_guided(settings_path=path, force=True)
    assert exit_code == 0
    data = json.loads(path.read_text())
    assert data.get("web_search_provider") == "serper"
    assert data.get("api_keys", {}).get("SERPER_API_KEY") == "sk-serper-test"
