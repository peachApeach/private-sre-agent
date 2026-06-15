from sre_agent.llm.providers.base import LLMProvider
from sre_agent.llm.providers.ollama import OllamaProvider
from sre_agent.llm.providers.openai_provider import OpenAIProvider
from sre_agent.llm.providers.openai_compat import OpenAICompatProvider
from sre_agent.llm.providers.anthropic_provider import AnthropicProvider

__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenAICompatProvider",
    "AnthropicProvider",
    "get_provider",
]


def get_provider(provider: str) -> "LLMProvider":
    mapping = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "openai-compat": OpenAICompatProvider,
        "vllm": OpenAICompatProvider,
        "lm-studio": OpenAICompatProvider,
        "anthropic": AnthropicProvider,
    }
    cls = mapping.get(provider)
    if cls is None:
        raise ValueError(
            f"지원하지 않는 LLM provider: '{provider}'. "
            f"지원 목록: {', '.join(mapping)}"
        )
    return cls()
