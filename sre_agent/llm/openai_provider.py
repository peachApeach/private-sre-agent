import os

from openai import OpenAI

from sre_agent.llm.prompts import build_summary_prompt


def summarize_with_openai(
    diagnosis: dict,
    model: str = "gpt-5.4-mini",
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    prompt = build_summary_prompt(diagnosis)

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    return response.output_text.strip()