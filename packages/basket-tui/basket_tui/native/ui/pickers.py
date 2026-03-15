"""
Prompt_toolkit overlay pickers for terminal-native TUI (sessions, agents, models).
"""

import json
import logging
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _fetch_sessions(http_base_url: str) -> list[dict[str, Any]]:
    """GET /api/sessions from gateway; return list of session dicts (session_id, created_at, etc.)."""
    url = f"{http_base_url.rstrip('/')}/api/sessions"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        logger.warning(
            "Fetch sessions failed",
            extra={
                "url": url,
                "error_type": type(e).__name__,
                "error": str(e),
            },
            exc_info=True,
        )
        return []


def run_session_picker(http_base_url: str) -> Optional[str]:
    """
    Full-screen prompt_toolkit list of sessions; return selected session_id or None on cancel.

    Fetches sessions from GET {http_base_url}/api/sessions. Displays with arrow keys,
    Enter to select, Esc to cancel.
    """
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import RadioList

    sessions = _fetch_sessions(http_base_url)
    if not sessions:
        logger.debug("Picker opening", extra={"kind": "session", "items_count": 0})
        print("[system] No sessions found.", flush=True)
        return None

    logger.debug(
        "Picker opening", extra={"kind": "session", "items_count": len(sessions)}
    )

    # Build choices: (session_id, label)
    choices: list[tuple[str, str]] = []
    for s in sessions:
        sid = s.get("session_id", "unknown")
        created = s.get("created_at", 0)
        total = s.get("total_messages", 0)
        label = f"  {sid[:12]}...  messages={total}  created={created}"
        choices.append((sid, label))

    selected: list[Optional[str]] = [None]
    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("escape")
    def _(event):  # noqa: B008
        selected[0] = None
        event.app.exit()

    radio = RadioList(values=choices)

    @kb.add("enter")
    def _(event):  # noqa: B008
        if radio.current_value is not None:
            selected[0] = radio.current_value
        event.app.exit()

    layout = Layout(
        HSplit(
            [
                Window(
                    height=1,
                    content=FormattedTextControl(
                        "Session (Enter select, Esc cancel)"
                    ),
                ),
                radio,
            ]
        )
    )
    app = Application(layout=layout, key_bindings=kb, full_screen=True)
    app.run()

    result = selected[0]
    logger.debug(
        "Picker closed", extra={"kind": "session", "result": result is not None}
    )
    if result:
        logger.debug("Picker item selected", extra={"kind": "session", "selection": result})

    return result


def _fetch_json_list(http_base_url: str, path: str) -> list:
    """GET {base}{path}, return JSON list or []."""
    url = f"{http_base_url.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(
            "Fetch failed",
            extra={
                "path": path,
                "url": url,
                "error_type": type(e).__name__,
                "error": str(e),
            },
            exc_info=True,
        )
        return []


def _fetch_agents(http_base_url: str) -> list[str]:
    """GET /api/agents; return list of agent names."""
    return _fetch_json_list(http_base_url, "/api/agents")


def _fetch_models(http_base_url: str) -> list[dict[str, Any]]:
    """GET /api/models; return list of {agent_name, model_id}."""
    return _fetch_json_list(http_base_url, "/api/models")


def _run_picker(
    title: str,
    choices: list[tuple[str, str]],
) -> Optional[str]:
    """Generic full-screen RadioList picker; return selected value or None."""
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import RadioList

    if not choices:
        return None
    selected: list[Optional[str]] = [None]
    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("escape")
    def _(event):  # noqa: B008
        selected[0] = None
        event.app.exit()

    radio = RadioList(values=choices)

    @kb.add("enter")
    def _(event):  # noqa: B008
        if radio.current_value is not None:
            selected[0] = radio.current_value
        event.app.exit()

    layout = Layout(
        HSplit(
            [
                Window(height=1, content=FormattedTextControl(title)),
                radio,
            ]
        )
    )
    app = Application(layout=layout, key_bindings=kb, full_screen=True)
    app.run()
    return selected[0]


def run_agent_picker(http_base_url: str) -> Optional[str]:
    """Show agent list from GET /api/agents; return selected agent_name or None."""
    names = _fetch_agents(http_base_url)
    if not names:
        logger.debug("Picker opening", extra={"kind": "agent", "items_count": 0})
        print("[system] No agents found.", flush=True)
        return None

    logger.debug("Picker opening", extra={"kind": "agent", "items_count": len(names)})
    choices = [(n, f"  {n}") for n in names]
    result = _run_picker("Agent (Enter select, Esc cancel)", choices)

    logger.debug("Picker closed", extra={"kind": "agent", "result": result is not None})
    if result:
        logger.debug("Picker item selected", extra={"kind": "agent", "selection": result})

    return result


def run_model_picker(http_base_url: str) -> Optional[str]:
    """
    Show model list from GET /api/models; return selected agent_name or None.

    Each item is (agent_name, model_id); selecting one switches to that agent (and its model).
    """
    items = _fetch_models(http_base_url)
    if not items:
        print("[system] No models found.", flush=True)
        return None
    choices: list[tuple[str, str]] = []
    for m in items:
        agent_name = m.get("agent_name", "default")
        model_id = m.get("model_id", "")
        choices.append((agent_name, f"  {agent_name}  —  {model_id}"))
    return _run_picker("Model (Enter select, Esc cancel)", choices)
