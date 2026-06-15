import os

import anthropic

from sre_agent.llm.prompts import build_log_analysis_prompt, build_summary_prompt
from sre_agent.llm.providers.base import LLMProvider

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(LLMProvider):
    def _client(self) -> anthropic.Anthropic:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        return anthropic.Anthropic(api_key=api_key)

    def summarize(self, diagnosis: dict, model: str = DEFAULT_MODEL) -> str:
        prompt = build_summary_prompt(diagnosis)
        message = self._client().messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def analyze_logs(self, logs: str, context: str, model: str = DEFAULT_MODEL) -> str:
        prompt = build_log_analysis_prompt(logs, context)
        message = self._client().messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def chat(self, messages: list[dict], model: str = DEFAULT_MODEL) -> str:
        # Anthropic API는 system 메시지를 별도 파라미터로 받음
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        user_messages = [m for m in messages if m["role"] != "system"]
        system_text = "\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN

        message = self._client().messages.create(
            model=model,
            max_tokens=2048,
            system=system_text,
            messages=user_messages,
        )
        return message.content[0].text.strip()
