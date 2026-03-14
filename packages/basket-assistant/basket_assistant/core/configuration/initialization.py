"""配置初始化向导：交互式配置创建"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from .models import ModelSettings, Settings
from .validation import ConfigValidator

if TYPE_CHECKING:
    from .manager import ConfigurationManager

logger = logging.getLogger(__name__)

# Provider 选项：(id, display_name, default_model, env_var)
PROVIDER_CHOICES = [
    ("openai", "OpenAI (GPT)", "gpt-4o-mini", "OPENAI_API_KEY"),
    ("anthropic", "Anthropic (Claude)", "claude-3-5-sonnet-20241022", "ANTHROPIC_API_KEY"),
    ("google", "Google (Gemini)", "gemini-1.5-pro", "GOOGLE_API_KEY"),
]

# Web 搜索选项
WEB_SEARCH_CHOICES = [
    ("duckduckgo", "duckduckgo（默认，无需 API Key）"),
    ("serper", "serper（Google 搜索，需 Serper API）"),
]

_INSTRUCTION_SELECT = "↑/↓ 移动，回车选中"

# 步骤条：已配置蓝色，未配置灰色
_WIZARD_STEP_TITLES = ("Provider", "API Key", "Model", "Base URL", "工作区", "Web 搜索")
_ANSI_BLUE = "\033[34m"
_ANSI_GRAY = "\033[90m"
_ANSI_RESET = "\033[0m"


def _print_stepper(current_1based: int, total: int = 6) -> None:
    """打印步骤条：圆点 + 竖线，已完成/当前为蓝色，未配置为灰色，行间空一行。"""
    for i in range(1, total + 1):
        is_done_or_current = i <= current_1based
        dot = _ANSI_BLUE + "•" + _ANSI_RESET if is_done_or_current else _ANSI_GRAY + "•" + _ANSI_RESET
        title = _WIZARD_STEP_TITLES[i - 1]
        print(f"  {dot}  {title}")
        if i < total:
            print("  " + _ANSI_GRAY + "│" + _ANSI_RESET)
        print()


class ConfigInitializer:
    """配置初始化向导"""

    def __init__(self, config_manager: ConfigurationManager):
        """
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self._validator = ConfigValidator()

    def run(self, force: bool = False) -> Settings:
        """
        运行 6 步初始化流程

        Args:
            force: 是否强制覆盖现有配置

        Returns:
            创建的配置

        Steps:
            1. Provider 选择
            2. API Key 输入（脱敏）
            3. Model 选择
            4. Base URL（可选）
            5. Workspace 目录（可选）
            6. Web 搜索配置
        """
        # Step 0: 检查覆盖确认
        if self.config_manager.exists() and not force:
            if not self._confirm_overwrite():
                logger.info("用户取消初始化")
                return self.config_manager.load()

        # 检查是否为交互模式
        use_interactive = self._use_interactive_mode()

        if not use_interactive:
            # 非交互模式：使用环境变量自动配置
            logger.info("非交互模式：使用环境变量自动配置")
            settings = self._create_from_environment()
        else:
            # 交互模式：6步向导
            logger.info("交互模式：启动配置向导")
            settings = self._run_interactive_wizard()
            if settings is None:
                logger.info("用户取消初始化")
                return self.config_manager.load()

        # 保存配置
        self.config_manager.save(settings)
        logger.info(f"配置已保存到: {self.config_manager.config_path}")

        return settings

    def _use_interactive_mode(self) -> bool:
        """检查是否使用交互模式"""
        if not sys.stdin.isatty():
            return False

        # 检查 questionary 是否可用
        try:
            import questionary  # noqa: F401
            return True
        except ImportError:
            logger.warning("questionary 未安装，使用非交互模式")
            return False

    def _confirm_overwrite(self) -> bool:
        """确认覆盖现有配置"""
        if not self._use_interactive_mode():
            return False

        path = self.config_manager.config_path
        try:
            import questionary
            from prompt_toolkit.styles import Style

            ok = questionary.confirm(
                f"配置文件已存在：{path}\n是否覆盖？",
                default=False,
                qmark="•",
                style=Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"}),
            ).ask()

            return ok is not None and ok
        except Exception as e:
            logger.error(f"确认覆盖失败: {e}")
            return False

    def _create_from_environment(self) -> Settings:
        """从环境变量创建配置（非交互模式）"""
        provider = "openai"
        api_key_var = "OPENAI_API_KEY"
        default_model = "gpt-4o-mini"

        for prov_id, _, model, env_var in PROVIDER_CHOICES:
            if os.environ.get(env_var):
                provider = prov_id
                api_key_var = env_var
                default_model = model
                break

        logger.info(f"检测到 {api_key_var}，使用 provider: {provider}")

        api_keys: Dict[str, str] = {}
        if os.environ.get(api_key_var):
            api_keys[provider] = os.environ[api_key_var]

        return Settings(
            model=ModelSettings(
                provider=provider,
                model_id=default_model,
            ),
            api_keys=api_keys,
        )

    def _run_interactive_wizard(self) -> Optional[Settings]:
        """运行交互式 6 步向导，返回 Settings 或 None（用户取消）。"""
        use_pretty = self._use_interactive_mode()
        style = None
        if use_pretty:
            try:
                from prompt_toolkit.styles import Style
                style = Style.from_dict({"qmark": "ansiblue", "question": "ansiblue"})
            except Exception:
                use_pretty = False

        # Step 1/6: Provider
        provider_id, _label, default_model, api_key_env = self._step_provider(use_pretty, style)
        if provider_id is None:
            return None

        # Step 2/6: API Key
        api_key = self._step_api_key(use_pretty, style, api_key_env)
        if api_key is None and api_key_env is not None:
            return None  # user cancelled
        api_key = (api_key or "").strip() or os.environ.get(api_key_env or "", "")

        # Step 3/6: Model
        model_id = self._step_model(use_pretty, style, default_model)
        if model_id is None:
            return None
        model_id = (model_id or "").strip() or default_model

        # Step 4/6: Base URL
        base_url = self._step_base_url(use_pretty, style)
        if base_url is None:
            return None
        base_url = (base_url or "").strip() or None

        # Step 5/6: Workspace
        workspace_dir = self._step_workspace(use_pretty, style)
        if workspace_dir is None:
            return None
        workspace_dir = (workspace_dir or "").strip() or None

        # Step 6/6: Web search
        web_search_provider, serper_key = self._step_web_search(use_pretty, style)
        if web_search_provider is None and serper_key is None:
            return None

        # Build api_keys (validator expects provider id: openai, anthropic, google)
        api_keys: Dict[str, str] = {}
        if api_key and provider_id:
            api_keys[provider_id] = api_key
        if web_search_provider == "serper" and serper_key:
            api_keys["SERPER_API_KEY"] = (serper_key or "").strip() or os.environ.get("SERPER_API_KEY", "")

        return Settings(
            model=ModelSettings(
                provider=provider_id,
                model_id=model_id,
                base_url=base_url,
            ),
            api_keys=api_keys,
            workspace_dir=workspace_dir,
            web_search_provider=web_search_provider if web_search_provider != "duckduckgo" else None,
        )

    def _step_provider(
        self, use_pretty: bool, style: Any
    ) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
        """Step 1/6: 选择 Provider。返回 (provider_id, label, default_model, api_key_env) 或 (None, None, '', None)。"""
        if use_pretty:
            import questionary
            print("\n\n")
            _print_stepper(1)
            choices = [
                questionary.Choice(label, value=i)
                for i, (_, label, _, _) in enumerate(PROVIDER_CHOICES)
            ]
            result = questionary.select(
                "1/6 选择 Provider",
                choices=choices,
                default=0,
                instruction=_INSTRUCTION_SELECT,
                qmark="•",
                style=style,
            ).ask()
            if result is None:
                return (None, None, "", None)
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

        t = PROVIDER_CHOICES[idx]
        return (t[0], t[1], t[2], t[3])

    def _step_api_key(
        self, use_pretty: bool, style: Any, api_key_env: Optional[str]
    ) -> Optional[str]:
        """Step 2/6: API Key 输入。返回 key 或 None（取消）。"""
        hint = f"留空则使用环境变量 {api_key_env}" if api_key_env else "输入 API Key"
        if use_pretty:
            import questionary
            print("\n\n")
            _print_stepper(2)
            api_key = questionary.password(
                "2/6 API Key",
                instruction=hint,
                qmark="•",
                style=style,
            ).ask()
            if api_key is None:
                return None
            api_key = (api_key or "").strip()
            if api_key and api_key_env:
                try:
                    prov = api_key_env.replace("_API_KEY", "").lower()
                    self._validator.validate_api_key(prov, api_key)
                except Exception as e:
                    print(f"  ⚠️  {e}")
            return api_key or None
        else:
            try:
                return input(f"API Key (leave empty to use env {api_key_env}): ").strip() or None
            except EOFError:
                return None

    def _step_model(
        self, use_pretty: bool, style: Any, default_model: str
    ) -> Optional[str]:
        """Step 3/6: Model ID。返回 model_id 或 None（取消）。"""
        if use_pretty:
            import questionary
            print("\n\n")
            _print_stepper(3)
            model_id = questionary.text(
                "3/6 Model",
                default=default_model,
                instruction="直接回车使用默认模型",
                qmark="•",
                style=style,
            ).ask()
            return model_id
        else:
            try:
                return input(f"Model (leave empty for {default_model}): ").strip() or default_model
            except EOFError:
                return default_model

    def _step_base_url(self, use_pretty: bool, style: Any) -> Optional[str]:
        """Step 4/6: Base URL。返回 base_url 或 None（取消）。"""
        if use_pretty:
            import questionary
            print("\n\n")
            _print_stepper(4)
            base_url = questionary.text(
                "4/6 Base URL（自建/代理端点）",
                default="",
                instruction="留空则使用官方端点",
                qmark="•",
                style=style,
            ).ask()
            return base_url
        else:
            try:
                return input("Base URL (leave empty to skip): ").strip() or ""
            except EOFError:
                return ""

    def _step_workspace(self, use_pretty: bool, style: Any) -> Optional[str]:
        """Step 5/6: 工作区目录。返回 path 或 None（取消）。"""
        if use_pretty:
            import questionary
            print("\n\n")
            _print_stepper(5)
            workspace_dir = questionary.text(
                "5/6 工作区目录（身份与行为文件）",
                default="",
                instruction="留空则跳过，使用默认路径",
                qmark="•",
                style=style,
            ).ask()
            return workspace_dir
        else:
            try:
                return input("Workspace directory (leave empty to skip): ").strip() or ""
            except EOFError:
                return ""

    def _step_web_search(
        self, use_pretty: bool, style: Any
    ) -> Tuple[Optional[str], Optional[str]]:
        """Step 6/6: Web 搜索。返回 (provider_id, serper_key) 或 (None, None) 表示取消。"""
        if use_pretty:
            import questionary
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
                style=style,
            ).ask()
            if web_result is None:
                return (None, None)
            web_search_provider = None if web_result == "duckduckgo" else "serper"
        else:
            print("\nWeb search:")
            print("  1) duckduckgo (default)")
            print("  2) serper (Google via Serper API)")
            try:
                web_choice = input("Choice [1]: ").strip() or "1"
            except EOFError:
                web_choice = "1"
            web_search_provider = "serper" if web_choice == "2" else None

        serper_key: Optional[str] = ""
        if web_search_provider == "serper":
            if use_pretty:
                serper_key = questionary.password(
                    "SERPER_API_KEY",
                    instruction="留空则使用环境变量 SERPER_API_KEY",
                    qmark="•",
                    style=style,
                ).ask()
                if serper_key is None:
                    return (None, None)
            else:
                try:
                    serper_key = input("SERPER_API_KEY (leave empty to use env): ").strip()
                except EOFError:
                    serper_key = ""
            serper_key = (serper_key or "").strip() or os.environ.get("SERPER_API_KEY", "")

        return (web_search_provider, serper_key)
