from __future__ import annotations

import os
from pathlib import Path

_CONFIG_PATH = Path.home() / ".sre-agent.yaml"

_DEFAULT_PROVIDER = "ollama"
_DEFAULT_MODELS: dict[str, str] = {
    "ollama": "qwen2.5:3b",
    "openai": "gpt-4o-mini",
    "openai-compat": "default",
    "vllm": "default",
    "lm-studio": "default",
    "anthropic": "claude-haiku-4-5-20251001",
}


def _load_yaml_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        import yaml  # PyYAML은 optional
        with _CONFIG_PATH.open() as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}
    except Exception:
        return {}


class AgentConfig:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        file_cfg = _load_yaml_config()

        # 우선순위: CLI 인자 > 환경변수 > 설정 파일 > 기본값
        self.provider: str = (
            provider
            or os.getenv("SRE_AGENT_PROVIDER")
            or file_cfg.get("provider")
            or _DEFAULT_PROVIDER
        )

        default_model = _DEFAULT_MODELS.get(self.provider, "default")
        self.model: str = (
            model
            or os.getenv("SRE_AGENT_MODEL")
            or file_cfg.get("model")
            or default_model
        )

        self.base_url: str | None = (
            base_url
            or os.getenv("SRE_AGENT_BASE_URL")
            or file_cfg.get("base_url")
        )

    def summarize(self, diagnosis: dict) -> str:
        from sre_agent.llm.providers import get_provider
        provider = get_provider(self.provider)
        return provider.summarize(diagnosis, model=self.model)

    def analyze_logs(self, logs: str, context: str) -> str:
        from sre_agent.llm.providers import get_provider
        provider = get_provider(self.provider)
        return provider.analyze_logs(logs, context, model=self.model)

    def chat(self, messages: list[dict]) -> str:
        from sre_agent.llm.providers import get_provider
        provider = get_provider(self.provider)
        return provider.chat(messages, model=self.model)
