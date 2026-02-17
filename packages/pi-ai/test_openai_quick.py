"""Quick test to verify OpenAI provider structure."""
import sys
sys.path.insert(0, '.')

from pi_ai.providers.openai_completions import OpenAICompletionsProvider
from pi_ai.types import Model

# Test instantiation
provider = OpenAICompletionsProvider()
print("✓ OpenAICompletionsProvider instantiated")

# Test model creation
model = Model(
    id="gpt-4",
    name="GPT-4",
    api="openai-completions",
    provider="openai",
    baseUrl="https://api.openai.com/v1",
    cost={"input": 0.15, "output": 0.6, "cacheRead": 0.075, "cacheWrite": 0.3},
    contextWindow=128000,
    maxTokens=4096,
)
print("✓ Model created")

# Test compat settings
compat = provider._get_compat(model)
print(f"✓ Compat settings: {compat}")

print("\n✅ All basic tests passed!")
