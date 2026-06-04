from sre_agent.llm.ollama import summarize_with_ollama


def summarize_with_provider(
    diagnosis: dict,
    provider: str = "ollama",
    model: str = "qwen2.5:3b",
) -> str:
    if provider == "ollama":
        return summarize_with_ollama(diagnosis, model=model)

    if provider == "openai":
        from sre_agent.llm.openai_provider import summarize_with_openai

        return summarize_with_openai(diagnosis, model=model)

    raise ValueError(f"Unsupported LLM provider: {provider}")