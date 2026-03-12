"""
Guided setup for basket: interactive prompts to create ~/.basket/settings.json.
OpenClaw-style wizard: questionary for all steps (select/text/password/path) when stdin is a TTY.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Default config path: env BASKET_SETTINGS_PATH or ~/.basket/settings.json
def _default_settings_path() -> Path:
    env = os.environ.get("BASKET_SETTINGS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".basket" / "settings.json").resolve()


PROVIDER_CHOICES = [
    ("openai", "OpenAI (GPT)", "gpt-4o-mini", "OPENAI_API_KEY"),
    ("anthropic", "Anthropic (Claude)", "claude-3-5-sonnet-20241022", "ANTHROPIC_API_KEY"),
    ("google", "Google (Gemini)", "gemini-1.5-pro", "GOOGLE_API_KEY"),
]

WEB_SEARCH_CHOICES = [
    ("duckduckgo", "duckduckgo（默认，无需 API Key）"),
    ("serper", "serper（Google 搜索，需 Serper API）"),
]

_INSTRUCTION_SELECT = "↑/↓ 移动，回车选中"

# 步骤条：已配置蓝色，未配置灰色，竖线连接，行间留空
_WIZARD_STEP_TITLES = ("Provider", "API Key", "Model", "Base URL", "工作区", "Web 搜索")
_ANSI_BLUE = "\033[34m"
_ANSI_GRAY = "\033[90m"
_ANSI_RESET = "\033[0m"


def _print_stepper(current_1based: int, total: int = 6) -> None:
    """打印步骤条：圆点 + 竖线，已完成/当前为蓝色，未配置为灰色，行间空一行."""
    for i in range(1, total + 1):
        is_done_or_current = i <= current_1based
        dot = _ANSI_BLUE + "•" + _ANSI_RESET if is_done_or_current else _ANSI_GRAY + "•" + _ANSI_RESET
        title = _WIZARD_STEP_TITLES[i - 1]
        print(f"  {dot}  {title}")
        if i < total:
            print("  " + _ANSI_GRAY + "│" + _ANSI_RESET)
        print()  # 行间留空


def _use_pretty_prompts() -> bool:
    """Use questionary wizard when stdin is a TTY and questionary is available."""
    if not sys.stdin.isatty():
        return False
    try:
        import questionary  # noqa: F401
        return True
    except ImportError:
        return False


def run_init_guided(
    settings_path: Path | str | None = None,
    force: bool = False,
) -> int:
    """
    Run interactive guided setup and write settings.json.

    Args:
        settings_path: Output file path; None uses BASKET_SETTINGS_PATH or ~/.basket/settings.json.
        force: If True, overwrite existing file without prompting.

    Returns:
        0 on success, 1 on abort or error.
    """
    path = Path(settings_path) if settings_path else _default_settings_path()
    use_pretty = _use_pretty_prompts()

    # Step 0: overwrite confirmation
    if path.exists() and not force:
        if use_pretty:
            import questionary
            from prompt_toolkit.styles import Style
            ok = questionary.confirm(
                f"配置文件已存在：{path}\n是否覆盖？",
                default=False,
                qmark="•",
                style=Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"}),
            ).ask()
            if ok is None or not ok:
                print("已取消。")
                return 1
        else:
            try:
                answer = input(f"Config already exists at {path}. Overwrite? [y/N]: ").strip().lower()
            except EOFError:
                return 1
            if answer not in ("y", "yes"):
                print("Aborted.")
                return 1

    # Step 1/6: Provider
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(1)
        provider_choices = [
            questionary.Choice(label, value=i)
            for i, (_, label, _, _) in enumerate(PROVIDER_CHOICES)
        ]
        result = questionary.select(
            "1/6 选择 Provider",
            choices=provider_choices,
            default=0,
            instruction=_INSTRUCTION_SELECT,
            qmark="•",
            style=_style,
        ).ask()
        if result is None:
            return 1
        idx = result
    else:
        print("\nProvider:")
        for i, (_, label, _, _) in enumerate(PROVIDER_CHOICES, 1):
            print(f"  {i}) {label}")
        try:
            raw = input("Choice [1]: ").strip() or "1"
            idx = int(raw)
            if idx < 1 or idx > len(PROVIDER_CHOICES):
                idx = 1
        except (ValueError, EOFError):
            idx = 1
        idx -= 1
    provider_id, _label, default_model, api_key_env = PROVIDER_CHOICES[idx]

    # Step 2/6: API Key（脱敏输入）
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(2)
        api_key = questionary.password(
            "2/6 API Key",
            instruction=f"留空则使用环境变量 {api_key_env}",
            qmark="•",
            style=_style,
        ).ask()
        if api_key is None:
            return 1
        api_key = (api_key or "").strip()
        if not api_key:
            api_key = os.environ.get(api_key_env, "")
    else:
        try:
            api_key = input(f"API Key (leave empty to use env {api_key_env}): ").strip()
        except EOFError:
            return 1
        if not api_key:
            api_key = os.environ.get(api_key_env, "")

    # Step 3/6: Model
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(3)
        model_id = questionary.text(
            "3/6 Model",
            default=default_model,
            instruction="直接回车使用默认模型",
            qmark="•",
            style=_style,
        ).ask()
        if model_id is None:
            return 1
        model_id = (model_id or "").strip() or default_model
    else:
        try:
            model_id = input(f"Model (leave empty for {default_model}): ").strip() or default_model
        except EOFError:
            model_id = default_model

    # Step 4/6: Base URL
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(4)
        base_url = questionary.text(
            "4/6 Base URL（自建/代理端点）",
            default="",
            instruction="留空则使用官方端点",
            qmark="•",
            style=_style,
        ).ask()
        if base_url is None:
            return 1
        base_url = (base_url or "").strip()
    else:
        try:
            base_url = input("Base URL for self-hosted endpoint (leave empty to skip): ").strip() or ""
        except EOFError:
            base_url = ""

    # Step 5/6: Workspace
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(5)
        workspace_dir = questionary.text(
            "5/6 工作区目录（身份与行为文件）",
            default="",
            instruction="留空则跳过，使用默认路径",
            qmark="•",
            style=_style,
        ).ask()
        if workspace_dir is None:
            return 1
        workspace_dir = (workspace_dir or "").strip() or None
    else:
        try:
            workspace_dir = input(
                "Workspace directory for identity files (leave empty to skip): "
            ).strip() or ""
        except EOFError:
            workspace_dir = ""
        workspace_dir = workspace_dir if workspace_dir else None

    # Step 6/6: Web search
    if use_pretty:
        import questionary
        from prompt_toolkit.styles import Style
        _style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
        print("\n\n")
        _print_stepper(6)
        web_choices = [
            questionary.Choice(WEB_SEARCH_CHOICES[0][1], value=WEB_SEARCH_CHOICES[0][0]),
            questionary.Choice(WEB_SEARCH_CHOICES[1][1], value=WEB_SEARCH_CHOICES[1][0]),
        ]
        web_result = questionary.select(
            "6/6 Web 搜索",
            choices=web_choices,
            default=WEB_SEARCH_CHOICES[0][0],
            instruction=_INSTRUCTION_SELECT,
            qmark="•",
            style=_style,
        ).ask()
        if web_result is None:
            return 1
        web_search_provider = None if web_result == "duckduckgo" else "serper"
    else:
        print("\nWeb search:")
        print("  1) duckduckgo (default, no API key)")
        print("  2) serper (Google via Serper API)")
        try:
            web_choice = input("Choice [1]: ").strip() or "1"
        except EOFError:
            web_choice = "1"
        web_search_provider = "serper" if web_choice == "2" else None

    serper_key = ""
    if web_search_provider == "serper":
        if use_pretty:
            import questionary
            from prompt_toolkit.styles import Style
            serper_key = questionary.password(
                "SERPER_API_KEY",
                instruction="留空则使用环境变量 SERPER_API_KEY",
                qmark="•",
                style=Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"}),
            ).ask()
            if serper_key is None:
                return 1
            serper_key = (serper_key or "").strip() or os.environ.get("SERPER_API_KEY", "")
        else:
            try:
                serper_key = input(
                    "SERPER_API_KEY (leave empty to use env): "
                ).strip() or os.environ.get("SERPER_API_KEY", "")
            except EOFError:
                pass

    # Build full schema compatible with SettingsManager / AssistantAgent
    api_keys: dict[str, str] = {}
    if api_key:
        api_keys[api_key_env] = api_key
    if serper_key:
        api_keys["SERPER_API_KEY"] = serper_key

    data: dict[str, Any] = {
        "model": {
            "provider": provider_id,
            "model_id": model_id,
            "temperature": 0.7,
            "max_tokens": 4096,
            "context_window": 128000,
            "base_url": base_url if base_url else None,
        },
        "agent": {
            "max_turns": 10,
            "auto_save": True,
            "verbose": False,
        },
        "permissions": {"default_mode": "default"},
        "api_keys": api_keys,
        "sessions_dir": "~/.basket/sessions",
        "trajectory_dir": None,
        "skills_dirs": [],
        "skills_include": [],
        "agents": {},
        "agents_dirs": [],
        "workspace_dir": workspace_dir,
        "skip_bootstrap": False,
        "web_search_provider": web_search_provider,
        "serve": None,
        "relay_url": None,
        "hooks": None,
        "custom": {},
    }

    # Remove None values for cleaner JSON where schema allows
    def clean(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    data["model"] = clean(data["model"])
    if data["model"].get("base_url") is None:
        data["model"].pop("base_url", None)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSettings written to {path}. You can run 'basket gateway start' to start.")
    if api_key:
        print("Note: API key was written to the config file; ensure file permissions are restricted.")
    return 0
