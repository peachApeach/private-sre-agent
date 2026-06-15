import requests

from sre_agent.llm.prompts import build_log_analysis_prompt, build_summary_prompt
from sre_agent.llm.providers.base import LLMProvider

DEFAULT_MODEL = "qwen2.5:3b"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"


class OllamaProvider(LLMProvider):
    def summarize(self, diagnosis: dict, model: str = DEFAULT_MODEL) -> str:
        prompt = build_summary_prompt(diagnosis)
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def analyze_logs(self, logs: str, context: str, model: str = DEFAULT_MODEL) -> str:
        prompt = build_log_analysis_prompt(logs, context)
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def chat(self, messages: list[dict], model: str = DEFAULT_MODEL) -> str:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json={"model": model, "messages": messages, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
