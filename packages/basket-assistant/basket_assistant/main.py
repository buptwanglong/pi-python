"""
Main entry point for the Basket CLI.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .agent import AssistantAgent
from .core import SettingsManager

logger = logging.getLogger(__name__)


async def main_async(args: Optional[list] = None) -> int:
    """
    Async main function.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    # Parse --debug early so we can enable DEBUG logging before other logic
    use_debug = "--debug" in args
    if use_debug:
        args = [a for a in args if a != "--debug"]

    # Configure logging: default write to ~/.basket/logs/ (INFO); --debug or LOG_LEVEL overrides level
    fmt = "%(asctime)s %(name)s: %(levelname)s: %(message)s"
    log_level_name = (os.environ.get("LOG_LEVEL") or "").upper()
    level = logging.INFO
    if use_debug:
        level = logging.DEBUG
    elif log_level_name:
        level = getattr(logging, log_level_name, level) or level
    log_dir = Path.home() / ".basket" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "basket.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt))
        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        for name in ("basket_tui.app", "basket_assistant.modes.tui"):
            logging.getLogger(name).setLevel(level)
        logging.getLogger("anthropic._base_client").setLevel(logging.INFO)
        logger.info("Log file: %s", log_file)
    except OSError as e:
        logger.debug("Could not create log file: %s", e)

    # Parse subcommand and simple arguments
    use_tui = len(args) >= 1 and args[0] == "tui"
    if use_tui:
        args = args[1:]

    use_plan_mode = "--plan" in args
    if use_plan_mode:
        args = [a for a in args if a != "--plan"]

    session_id_arg: Optional[str] = None
    if "--session" in args:
        i = args.index("--session")
        if i + 1 < len(args):
            session_id_arg = args[i + 1]
            args = args[:i] + args[i + 2:]
        else:
            args = [a for a in args if a != "--session"]

    if "--permission-mode" in args:
        i = args.index("--permission-mode")
        if i + 1 < len(args) and args[i + 1] == "plan":
            use_plan_mode = True
        args = args[:i] + args[i + 2:] if i + 1 < len(args) else args[:i]

    tui_max_cols: Optional[int] = None
    tui_live_rows: Optional[int] = None
    if use_tui:
        if "--max-cols" in args:
            i = args.index("--max-cols")
            if i + 1 < len(args):
                try:
                    tui_max_cols = int(args[i + 1])
                except ValueError:
                    pass
                args = args[:i] + args[i + 2:]
        if "--live-rows" in args:
            i = args.index("--live-rows")
            if i + 1 < len(args):
                try:
                    tui_live_rows = int(args[i + 1])
                except ValueError:
                    pass
                args = args[:i] + args[i + 2:]

    use_remote = "--remote" in args
    if use_remote:
        args = [a for a in args if a != "--remote"]
    remote_bind = os.environ.get("BASKET_REMOTE_BIND", "0.0.0.0")
    remote_port = 7681
    try:
        remote_port = int(os.environ.get("BASKET_REMOTE_PORT", "7681"))
    except ValueError:
        pass
    if "--bind" in args:
        i = args.index("--bind")
        if i + 1 < len(args):
            remote_bind = args[i + 1]
            args = args[:i] + args[i + 2:]
    if "--port" in args:
        i = args.index("--port")
        if i + 1 < len(args):
            try:
                remote_port = int(args[i + 1])
            except ValueError:
                pass
            args = args[:i] + args[i + 2:]

    if "--help" in args or "-h" in args:
        print("""
Basket - AI-powered personal assistant

Usage:
  basket                 - Start interactive mode
  basket tui             - Start TUI (starts gateway if needed, then connect)
  basket --session <id> - Start with session loaded (use with interactive or tui)
  basket --remote        - Start remote web terminal (requires basket-remote, ttyd; use with ZeroTier)
  basket "message"       - Run once with a message
  basket --plan          - Run in plan mode (read-only; same as --permission-mode plan)
  basket gateway start   - Start resident assistant (gateway)
  basket gateway stop    - Stop resident assistant
  basket gateway status  - Show assistant status
  basket relay [url]      - Connect to relay (outbound only); url from settings.json relay_url or arg
  basket init             - Guided setup (create or overwrite settings.json)
  basket agent list|add|remove - Manage subagents (Task tool)
  basket --help          - Show this help
  basket --version       - Show version
  basket --debug         - Enable DEBUG logging (to log file only)

Interactive mode commands:
  help      - Show help
  settings  - Show settings
  exit/quit - Exit

Environment variables:
  OPENAI_API_KEY        - OpenAI API key
  ANTHROPIC_API_KEY     - Anthropic API key
  GOOGLE_API_KEY        - Google API key
  LOG_LEVEL             - Log level (e.g. DEBUG); overridden by --debug
  BASKET_REMOTE_BIND    - Bind address for --remote (default: 0.0.0.0)
  BASKET_REMOTE_PORT    - Port for --remote (default: 7681)
  BASKET_SERVE_PORT     - Port for resident assistant (default: 7682)
""")
        return 0

    if "--version" in args or "-v" in args:
        print("Basket v0.1.0")
        return 0

    # Init: guided setup
    if len(args) >= 1 and args[0] == "init":
        rest = args[1:]
        force = "--force" in rest
        rest = [a for a in rest if a != "--force"]
        path_arg = None
        if "--path" in rest:
            i = rest.index("--path")
            if i + 1 < len(rest):
                path_arg = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
            else:
                rest = rest[:i] + rest[i + 1:]
        from .init_guided import run_init_guided
        return run_init_guided(settings_path=path_arg, force=force)

    # Agent subcommands: list | add | remove (subagents for Task tool)
    if len(args) >= 1 and args[0] == "agent":
        from . import agent_cli
        rest = args[1:]
        if len(rest) == 0 or rest[0] in ("--help", "-h"):
            print("Usage: basket agent <list|add|remove> [options]")
            print("  list              List subagents in settings.json")
            print("  add               Add a subagent (--name, --description, --prompt; optional --tools, --force)")
            print("  remove <name>     Remove a subagent")
            print("  --path <file>     Use given settings file (default: BASKET_SETTINGS_PATH or ~/.basket/settings.json)")
            return 0
        sub = rest[0]
        rest = rest[1:]
        path_arg = None
        if "--path" in rest:
            i = rest.index("--path")
            if i + 1 < len(rest):
                path_arg = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
            else:
                rest = rest[:i] + rest[i + 1:]
        if sub == "list":
            return agent_cli.run_list(settings_path=path_arg)
        if sub == "remove":
            if not rest:
                print("Usage: basket agent remove <name>")
                return 1
            return agent_cli.run_remove(rest[0], settings_path=path_arg)
        if sub == "add":
            force = "--force" in rest
            rest = [a for a in rest if a != "--force"]
            name = None
            description = None
            prompt = None
            tools_s = None
            i = 0
            while i < len(rest):
                if rest[i] == "--name" and i + 1 < len(rest):
                    name = rest[i + 1]
                    rest = rest[:i] + rest[i + 2:]
                    continue
                if rest[i] == "--description" and i + 1 < len(rest):
                    description = rest[i + 1]
                    rest = rest[:i] + rest[i + 2:]
                    continue
                if rest[i] == "--prompt" and i + 1 < len(rest):
                    prompt = rest[i + 1]
                    rest = rest[:i] + rest[i + 2:]
                    continue
                if rest[i] == "--tools" and i + 1 < len(rest):
                    tools_s = rest[i + 1]
                    rest = rest[:i] + rest[i + 2:]
                    continue
                i += 1
            if not name:
                try:
                    name = input("Subagent name: ").strip()
                except EOFError:
                    return 1
                if not name:
                    print("Name is required.")
                    return 1
            if not description:
                try:
                    description = input("Description (short): ").strip()
                except EOFError:
                    return 1
                if not description:
                    print("Description is required.")
                    return 1
            if not prompt:
                try:
                    prompt = input("Prompt (system prompt for this subagent): ").strip()
                except EOFError:
                    return 1
                if not prompt:
                    print("Prompt is required.")
                    return 1
            tools_dict = agent_cli.parse_tools(tools_s) if tools_s else None
            return agent_cli.run_add(
                name=name,
                description=description,
                prompt=prompt,
                tools_dict=tools_dict,
                force=force,
                settings_path=path_arg,
            )
        print("Usage: basket agent <list|add|remove> [options]")
        return 1

    # Gateway subcommands: resident assistant (start / stop / status / attach)
    def _build_serve_channel_config():
        """Build channel_config from settings.json (serve). Assistant does not interpret channel schema; gateway/channels do."""
        cfg = {"websocket": True, "feishu": None}
        try:
            sm = SettingsManager()
            settings = sm.load()
            if getattr(settings, "serve", None) and isinstance(settings.serve, dict):
                cfg.update(settings.serve)
        except Exception as e:
            logger.debug("Loading serve channel config: %s", e)
        return cfg

    if len(args) >= 2 and args[0] == "gateway" and args[1] in ("start", "stop", "status"):
        sub = args[1]
        rest = args[2:]
        if sub == "start":
            foreground = "--foreground" in rest
            rest = [a for a in rest if a != "--foreground"]
            if rest:
                print("Usage: basket gateway start [--foreground]")
                return 1
            try:
                from .serve import run_gateway, is_serve_running
            except ImportError as e:
                logger.warning("serve import failed: %s", e)
                print("Error: basket gateway requires starlette and uvicorn.")
                print("Install with: poetry add starlette 'uvicorn[standard]'")
                return 1
            running, pid = is_serve_running()
            if running:
                print(f"Assistant is already running (pid {pid}). Use 'basket gateway stop' first.")
                return 1
            port = 7682
            try:
                port = int(os.environ.get("BASKET_SERVE_PORT", "7682"))
            except ValueError:
                pass
            if not foreground:
                print("Starting assistant in foreground. Use Ctrl+C to stop.")
                print("Tip: run with 'nohup basket gateway start &' or systemd for background.")
            channel_config = _build_serve_channel_config()
            await run_gateway(
                host="127.0.0.1",
                port=port,
                agent_factory=AssistantAgent,
                channel_config=channel_config,
            )
            return 0
        if sub == "stop":
            try:
                from .serve import read_serve_state, clear_serve_state, is_serve_running
            except ImportError:
                print("Error: basket gateway requires the serve module.")
                return 1
            import signal
            pid, _ = read_serve_state()
            if pid is None:
                print("Assistant is not running (no pid file).")
                return 0
            running, _ = is_serve_running()
            if not running:
                print("Assistant is not running (stale pid file removed).")
                clear_serve_state()
                return 0
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as e:
                print(f"Error stopping assistant: {e}")
                return 1
            print(f"Sent SIGTERM to pid {pid}. Waiting for exit...")
            for _ in range(30):
                await asyncio.sleep(0.5)
                if not is_serve_running()[0]:
                    break
            clear_serve_state()
            print("Assistant stopped.")
            return 0
        if sub == "status":
            try:
                from .serve import read_serve_state, is_serve_running
            except ImportError:
                print("Error: basket gateway requires the serve module.")
                return 1
            running, pid = is_serve_running()
            _, port = read_serve_state()
            if not running:
                print("Assistant is not running.")
                return 0
            print(f"Assistant is running (pid {pid}, port {port}).")
            if port is not None:
                try:
                    import urllib.request
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/status")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        data = json.load(resp)
                        if "uptime_seconds" in data:
                            print(f"Uptime: {data['uptime_seconds']}s")
                        if "version" in data:
                            print(f"Version: {data['version']}")
                except Exception:
                    pass
            return 0

    # Remote mode: run ttyd with basket tui, no agent in this process
    if use_remote:
        if len(args) > 0:
            print("Remote mode does not support one-shot messages. Run: basket --remote [--bind <IP>] [--port <port>]")
            return 1
        try:
            from basket_remote import run_serve
        except ImportError as e:
            logger.warning("basket_remote import failed: %s", e)
            print("Error: Remote mode requires 'basket-remote' package.")
            print("Install with: poetry add basket-remote")
            return 1
        command = [sys.executable, "-m", "basket_assistant.main", "tui"]
        try:
            run_serve(bind=remote_bind, port=remote_port, command=command)
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1
        return 0

    # Relay mode: outbound-only, no local port
    if len(args) >= 1 and args[0] == "relay":
        relay_url = args[1] if len(args) >= 2 else None
        if not relay_url:
            _settings = SettingsManager().load()
            relay_url = getattr(_settings, "relay_url", None) or (
                (_settings.serve or {}).get("relay_url") if _settings.serve else None
            )
        if not relay_url:
            print("Usage: basket relay <relay_url>  (or set relay_url in ~/.basket/settings.json)")
            print("Example: basket relay wss://your-vps:7683/relay/agent")
            return 1
        try:
            from .modes.relay_client import run_relay_client
        except ImportError as e:
            logger.warning("relay_client import failed: %s", e)
            print("Error: basket relay requires 'websockets' package.")
            print("Install with: poetry add websockets")
            return 1
        await run_relay_client(relay_url)
        return 0

    # TUI mode: ensure gateway is running, then connect TUI to it (no local agent)
    if use_tui:
        try:
            from .serve import get_serve_port, is_serve_running, read_serve_state
            from .modes.attach import run_tui_mode_attach
        except ImportError as e:
            logger.warning("TUI/attach import failed: %s", e)
            print(f"Error: TUI requires 'basket-tui' and gateway support: {e}")
            return 1
        port = 7682
        try:
            port = int(os.environ.get("BASKET_SERVE_PORT", "7682"))
        except ValueError:
            pass
        running, _ = is_serve_running()
        if not running:
            # Start gateway in background subprocess
            proc = subprocess.Popen(
                [sys.executable, "-m", "basket_assistant.main", "gateway", "start"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Wait for gateway to write state and be ready (poll up to ~15s)
            for _ in range(30):
                await asyncio.sleep(0.5)
                running, _ = is_serve_running()
                _, port_from_state = read_serve_state()
                if running and port_from_state is not None:
                    port = port_from_state
                    break
            if not running:
                try:
                    proc.terminate()
                except Exception:
                    pass
                print("Error: Failed to start gateway in time.")
                return 1
        else:
            port = get_serve_port() or port
        attach_url = f"ws://127.0.0.1:{port}/ws"
        await run_tui_mode_attach(attach_url)
        return 0

    # Create agent (CLI --agent sets BASKET_AGENT for main-agent model selection)
    try:
        agent_name = os.environ.get("BASKET_AGENT") or None
        agent = AssistantAgent(agent_name=agent_name)
    except Exception as e:
        logger.exception("Failed to initialize agent")
        print(f"Error initializing agent: {e}")
        return 1

    if use_plan_mode:
        agent.set_plan_mode(True)

    if session_id_arg:
        sessions = await agent.session_manager.list_sessions()
        if not any(s.session_id == session_id_arg for s in sessions):
            print(f"Session not found: {session_id_arg}")
            return 1
        await agent.set_session_id(session_id_arg, load_history=True)

    # Run mode (interactive or one-shot; TUI is handled above via gateway attach)
    if len(args) == 0:
        await agent.run_interactive()
    else:
        # One-shot mode
        message = " ".join(args)
        response = await agent.run_once(message)
        print(response)

    return 0


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
