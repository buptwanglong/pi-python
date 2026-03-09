"""
Guided setup for basket: interactive prompts to create ~/.basket/settings.json.
"""

from __future__ import annotations

import json
import os
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

    # Step 0: overwrite confirmation
    if path.exists() and not force:
        try:
            answer = input(f"Config already exists at {path}. Overwrite? [y/N]: ").strip().lower()
        except EOFError:
            return 1
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    # Step 1: Provider
    print("\nProvider:")
    for i, (pid, label, _model, _key) in enumerate(PROVIDER_CHOICES, 1):
        print(f"  {i}) {label}")
    try:
        raw = input("Choice [1]: ").strip() or "1"
        idx = int(raw)
        if idx < 1 or idx > len(PROVIDER_CHOICES):
            idx = 1
    except (ValueError, EOFError):
        idx = 1
    provider_id, _label, default_model, api_key_env = PROVIDER_CHOICES[idx - 1]

    # Step 2: API Key
    try:
        api_key = input(
            f"API Key (leave empty to use env {api_key_env}): "
        ).strip()
    except EOFError:
        return 1
    if not api_key:
        api_key = os.environ.get(api_key_env, "")

    # Step 3: Model
    try:
        model_id = input(f"Model (leave empty for {default_model}): ").strip() or default_model
    except EOFError:
        model_id = default_model

    # Step 4: Base URL
    try:
        base_url = input("Base URL for self-hosted endpoint (leave empty to skip): ").strip() or ""
    except EOFError:
        base_url = ""

    # Step 5: Workspace directory
    try:
        workspace_dir = input(
            "Workspace directory for identity files (leave empty to skip): "
        ).strip() or ""
    except EOFError:
        workspace_dir = ""
    workspace_dir = workspace_dir if workspace_dir else None

    # Step 6: Web search
    print("\nWeb search:")
    print("  1) duckduckgo (default, no API key)")
    print("  2) serper (Google via Serper API)")
    try:
        web_choice = input("Choice [1]: ").strip() or "1"
    except EOFError:
        web_choice = "1"
    web_search_provider: str | None = "serper" if web_choice == "2" else None
    serper_key = ""
    if web_search_provider == "serper":
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

    print(f"\nSettings written to {path}. You can run 'basket' to start.")
    if api_key:
        print("Note: API key was written to the config file; ensure file permissions are restricted.")
    return 0
