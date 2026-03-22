"""Tests for native pickers."""

from unittest.mock import patch

import pytest

from basket_tui.native.ui.pickers import (
    _fetch_agents,
    _fetch_models,
    _fetch_plugins,
    _fetch_sessions,
)


def test_fetch_sessions_returns_list():
    with patch("urllib.request.urlopen") as mock_open:
        resp = mock_open.return_value.__enter__.return_value
        resp.read.return_value = b"[]"
        result = _fetch_sessions("http://127.0.0.1:7682")
    assert result == []


def test_fetch_sessions_parses_session_list():
    import json as _json
    payload = [
        {"session_id": "abc123", "created_at": 1000, "total_messages": 5},
    ]
    with patch("urllib.request.urlopen") as mock_open:
        resp = mock_open.return_value.__enter__.return_value
        resp.read.return_value = _json.dumps(payload).encode()
        result = _fetch_sessions("http://127.0.0.1:7682")
    assert len(result) == 1
    assert result[0]["session_id"] == "abc123"
    assert result[0]["total_messages"] == 5


def test_fetch_sessions_on_error_returns_empty_list():
    with patch("urllib.request.urlopen", side_effect=Exception("network error")):
        result = _fetch_sessions("http://127.0.0.1:7682")
    assert result == []


def test_fetch_agents_returns_list():
    with patch("urllib.request.urlopen") as mock_open:
        resp = mock_open.return_value.__enter__.return_value
        resp.read.return_value = b'["default", "explore"]'
        result = _fetch_agents("http://127.0.0.1:7682")
    assert result == ["default", "explore"]


def test_fetch_models_returns_list():
    import json as _json
    payload = [{"agent_name": "default", "model_id": "gpt-4"}]
    with patch("urllib.request.urlopen") as mock_open:
        resp = mock_open.return_value.__enter__.return_value
        resp.read.return_value = _json.dumps(payload).encode()
        result = _fetch_models("http://127.0.0.1:7682")
    assert len(result) == 1
    assert result[0]["agent_name"] == "default"
    assert result[0]["model_id"] == "gpt-4"


def test_fetch_plugins_returns_list():
    import json as _json
    payload = [{"name": "demo", "version": "1.0.0", "description": "test"}]
    with patch("urllib.request.urlopen") as mock_open:
        resp = mock_open.return_value.__enter__.return_value
        resp.read.return_value = _json.dumps(payload).encode()
        result = _fetch_plugins("http://127.0.0.1:7682")
    assert len(result) == 1
    assert result[0]["name"] == "demo"
    assert result[0]["version"] == "1.0.0"
