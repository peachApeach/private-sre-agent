import requests

from sre_agent.llm.prompts import build_summary_prompt

OLLAMA_URL = "http://localhost:11434/api/generate"


def summarize_with_ollama(
    analysis: dict,
    model: str = "qwen2.5:3b",
    timeout: int = 180,
) -> str:
    prompt = build_summary_prompt(analysis)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()

    return response.json()["response"].strip()