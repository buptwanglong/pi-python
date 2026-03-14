#!/usr/bin/env python3
"""
ConfigInitializer 使用示例

演示如何使用新的 ConfigInitializer 类初始化配置。
"""

import os
import sys
from pathlib import Path

# 添加 basket_assistant 到 Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from basket_assistant.core.configuration import ConfigurationManager, ConfigInitializer


def example_non_interactive():
    """示例 1: 非交互模式（CI/测试环境）"""
    print("=" * 60)
    print("示例 1: 非交互模式")
    print("=" * 60)

    # 使用临时配置文件
    config_path = Path("/tmp/basket_test_settings.json")

    # 设置环境变量
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-example-key-12345"

    # 创建配置管理器和初始化器
    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    # 运行初始化（非交互模式）
    settings = initializer.run(force=True)

    print(f"\n✅ 配置已创建:")
    print(f"   - Provider: {settings.model.provider}")
    print(f"   - Model: {settings.model.model_id}")
    print(f"   - API Keys: {list(settings.api_keys.keys())}")
    print(f"   - Config file: {config_path}")

    # 清理
    if config_path.exists():
        config_path.unlink()


def example_detect_openai():
    """示例 2: 检测 OpenAI API Key"""
    print("\n" + "=" * 60)
    print("示例 2: 检测 OpenAI API Key")
    print("=" * 60)

    config_path = Path("/tmp/basket_test_openai.json")

    # 只设置 OpenAI key
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["OPENAI_API_KEY"] = "sk-proj-example-key-12345"

    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    settings = initializer.run(force=True)

    print(f"\n✅ 配置已创建:")
    print(f"   - Provider: {settings.model.provider}")
    print(f"   - Model: {settings.model.model_id}")
    print(f"   - API Keys: {list(settings.api_keys.keys())}")

    # 清理
    if config_path.exists():
        config_path.unlink()


def example_no_api_key():
    """示例 3: 没有 API Key 的默认配置"""
    print("\n" + "=" * 60)
    print("示例 3: 没有 API Key 的默认配置")
    print("=" * 60)

    config_path = Path("/tmp/basket_test_no_key.json")

    # 清除所有 API Key
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
        os.environ.pop(key, None)

    config_manager = ConfigurationManager(config_path)
    initializer = ConfigInitializer(config_manager)

    settings = initializer.run(force=True)

    print(f"\n✅ 配置已创建:")
    print(f"   - Provider: {settings.model.provider}")
    print(f"   - Model: {settings.model.model_id}")
    print(f"   - API Keys: {list(settings.api_keys.keys()) or 'None'}")
    print(f"   ⚠️  注意: 需要手动设置 API Key 或环境变量才能使用")

    # 清理
    if config_path.exists():
        config_path.unlink()


def example_force_overwrite():
    """示例 4: 强制覆盖现有配置"""
    print("\n" + "=" * 60)
    print("示例 4: 强制覆盖现有配置")
    print("=" * 60)

    config_path = Path("/tmp/basket_test_overwrite.json")

    # 创建初始配置
    config_manager = ConfigurationManager(config_path)
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-old-key"
    initializer = ConfigInitializer(config_manager)
    settings1 = initializer.run(force=True)
    print(f"\n1️⃣ 初始配置:")
    print(f"   - Provider: {settings1.model.provider}")

    # 改变环境变量后强制覆盖
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["OPENAI_API_KEY"] = "sk-new-key"
    settings2 = initializer.run(force=True)
    print(f"\n2️⃣ 覆盖后的配置:")
    print(f"   - Provider: {settings2.model.provider}")

    # 清理
    if config_path.exists():
        config_path.unlink()


if __name__ == "__main__":
    print("\n🎯 ConfigInitializer 使用示例\n")

    try:
        example_non_interactive()
        example_detect_openai()
        example_no_api_key()
        example_force_overwrite()

        print("\n" + "=" * 60)
        print("✅ 所有示例运行成功！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
