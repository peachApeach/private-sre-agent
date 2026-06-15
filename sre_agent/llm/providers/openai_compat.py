import os

from openai import OpenAI

from sre_agent.llm.prompts import build_log_analysis_prompt, build_summary_prompt
from sre_agent.llm.providers.base import LLMProvider

DEFAULT_MODEL = "default"


class OpenAICompatProvider(LLMProvider):
    """vLLM, LM Studio, Ollama /v1, 사용자 정의 HTTP 서버 등 OpenAI 호환 엔드포인트."""

    def _client(self) -> OpenAI:
        base_url = os.getenv("SRE_AGENT_BASE_URL")
        if not base_url:
            raise RuntimeError(
                "openai-compat provider는 SRE_AGENT_BASE_URL 환경변수가 필요합니다. "
                "예: http://localhost:8000/v1"
            )
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY", "none"), base_url=base_url)

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
