import os

from openai import OpenAI

from sre_agent.llm.prompts import build_log_analysis_prompt, build_summary_prompt
from sre_agent.llm.providers.base import LLMProvider

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    def _client(self) -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        return OpenAI(api_key=api_key)

    def summarize(self, diagnosis: dict, model: str = DEFAULT_MODEL) -> str:
        prompt = build_summary_prompt(diagnosis)
        response = self._client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def analyze_logs(self, logs: str, context: str, model: str = DEFAULT_MODEL) -> str:
        prompt = build_log_analysis_prompt(logs, context)
        response = self._client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def chat(self, messages: list[dict], model: str = DEFAULT_MODEL) -> str:
        response = self._client().chat.completions.create(
            model=model,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
