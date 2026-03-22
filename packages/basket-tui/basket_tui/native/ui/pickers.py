"""
Prompt_toolkit overlay pickers for terminal-native TUI (sessions, agents, models, plugins).

Plugin list uses GET /api/plugins; install uses WebSocket ``plugin_install`` (not LLM).
"""

import asyncio
import json
import logging
import urllib.request
from collections.abc import Callable
from typing import Any, Literal, Optional

from ..connection.types import GatewayConnectionProtocol

logger = logging.getLogger(__name__)

PluginSlashResult = Literal["send", "handled"]

# Kept in sync with basket_assistant.commands.builtin.plugin.handle_plugin usage text.
PLUGIN_HELP_LINES: tuple[str, ...] = (
    "[system] Usage: /plugin <list|install|uninstall>",
    "  /plugin list, /plugins           Open plugin list (from gateway API)",
    "  /plugin install <source> [ref]   Install via WebSocket (local/zip/https/git)",
    "                                   Optional ref: second token or URL#tag (git only)",
    "  /plugin uninstall <name>         Sent to gateway as a slash command",
)


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


async def run_session_picker(http_base_url: str) -> Optional[str]:
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
    await app.run_async()

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


def _fetch_plugins(http_base_url: str) -> list[dict[str, Any]]:
    """GET /api/plugins; return list of {name, version, description}."""
    return _fetch_json_list(http_base_url, "/api/plugins")


async def _run_picker(
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
    await app.run_async()
    return selected[0]


async def run_agent_picker(http_base_url: str) -> Optional[str]:
    """Show agent list from GET /api/agents; return selected agent_name or None."""
    names = _fetch_agents(http_base_url)
    if not names:
        logger.debug("Picker opening", extra={"kind": "agent", "items_count": 0})
        print("[system] No agents found.", flush=True)
        return None

    logger.debug("Picker opening", extra={"kind": "agent", "items_count": len(names)})
    choices = [(n, f"  {n}") for n in names]
    result = await _run_picker("Agent (Enter select, Esc cancel)", choices)

    logger.debug("Picker closed", extra={"kind": "agent", "result": result is not None})
    if result:
        logger.debug("Picker item selected", extra={"kind": "agent", "selection": result})

    return result


async def run_model_picker(http_base_url: str) -> Optional[str]:
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
    return await _run_picker("Model (Enter select, Esc cancel)", choices)


async def run_plugin_list_picker(
    http_base_url: str,
    output_put: Callable[[str], None],
) -> None:
    """Fetch plugins from gateway, full-screen list; on Enter append details to ``output_put``."""
    plugins = _fetch_plugins(http_base_url)
    if not plugins:
        output_put("[system] No plugins installed.")
        return

    logger.debug("Picker opening", extra={"kind": "plugin", "items_count": len(plugins)})
    choices: list[tuple[str, str]] = []
    for p in plugins:
        name = str(p.get("name", "unknown"))
        ver = str(p.get("version", ""))
        desc = (p.get("description") or "").strip()
        label = f"  {name}  v{ver}"
        if desc:
            short = desc[:56] + ("…" if len(desc) > 56 else "")
            label += f"  — {short}"
        choices.append((name, label))

    selected = await _run_picker("Plugins (Enter select, Esc cancel)", choices)
    logger.debug("Picker closed", extra={"kind": "plugin", "result": selected is not None})
    if not selected:
        return
    info = next((x for x in plugins if str(x.get("name")) == selected), {})
    output_put(f"[system] Plugin: {info.get('name', selected)}")
    output_put(f"  version: {info.get('version', '')}")
    if info.get("description"):
        output_put(f"  description: {info['description']}")


async def handle_plugin_slash_line(
    text: str,
    http_base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: Callable[[str], None],
) -> PluginSlashResult | None:
    """Handle ``/plugin`` / ``/plugins`` for native TUI. Return ``None`` to forward the line as chat."""
    parts = text.strip().split(maxsplit=1)
    cmd0 = (parts[0] or "").lower()
    if cmd0 not in ("/plugin", "/plugins"):
        return None

    if cmd0 == "/plugins":
        await run_plugin_list_picker(http_base_url, output_put)
        return "handled"

    if len(parts) == 1:
        for line in PLUGIN_HELP_LINES:
            output_put(line)
        return "handled"

    rest = parts[1].strip()
    rest_parts = rest.split(maxsplit=1)
    sub = (rest_parts[0] or "").lower()
    sub_args = rest_parts[1].strip() if len(rest_parts) > 1 else ""

    if sub == "list":
        await run_plugin_list_picker(http_base_url, output_put)
        return "handled"
    if sub == "install":
        if not sub_args:
            output_put(
                "[system] Usage: /plugin install <path|zip|https-url|git-url> [git-ref]"
            )
            return "handled"
        try:
            asyncio.get_running_loop().create_task(
                connection.send_plugin_install(sub_args)
            )
        except Exception as e:
            output_put(f"[system] Failed: {e}")
        return "handled"

    return None
