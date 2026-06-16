"""LLM tool-use 에이전트 루프."""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from sre_agent.agent.tools import TOOL_SCHEMAS, run_tool
from sre_agent.config import AgentConfig

console = Console()

MAX_TURNS = 12

_SYSTEM_PROMPT = """\
You are an expert SRE. Respond ONLY in Korean (한국어). Do not use English in your response.
너는 Kubernetes 장애를 직접 조사하는 SRE 전문가다. 반드시 한국어로만 답해라.

주어진 kubectl tool을 사용해 스스로 조사하라:
1. Pod 상태, 이벤트, 로그를 확인해 장애 원인을 파악한다.
2. 로그에서 단서를 발견하면 관련 Pod/Deployment도 추가 조회할 수 있다.
3. 충분히 조사됐다고 판단하면 아래 형식으로 최종 리포트를 작성하고 tool 호출을 멈춰라.

최종 리포트 형식:
## 조사 요약
## 발견된 문제
## 원인 후보
## 즉시 확인할 것
"""


# ── provider별 tool call 실행 ──

def _run_openai_loop(config: AgentConfig, initial_message: str) -> str:
    from openai import OpenAI
    import os

    provider_name = config.provider
    if provider_name in ("openai-compat", "vllm", "lm-studio"):
        base_url = config.base_url or os.getenv("SRE_AGENT_BASE_URL")
        if not base_url:
            raise RuntimeError("openai-compat provider는 SRE_AGENT_BASE_URL 환경변수가 필요합니다.")
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "none"), base_url=base_url)
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        client = OpenAI(api_key=api_key)

    tools = [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["parameters"],
            },
        }
        for s in TOOL_SCHEMAS
    ]

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": initial_message},
    ]

    for turn in range(MAX_TURNS):
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=False))

        if not msg.tool_calls:
            return msg.content or ""

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            console.print(f"  [dim]→ {name}({_fmt_args(args)})[/dim]")
            output = run_tool(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output,
            })

    return "[에이전트] 최대 턴 수에 도달했습니다. 마지막 응답을 반환합니다."


def _run_anthropic_loop(config: AgentConfig, initial_message: str) -> str:
    import os
    import anthropic as _anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    client = _anthropic.Anthropic(api_key=api_key)

    tools = [
        {
            "name": s["name"],
            "description": s["description"],
            "input_schema": s["parameters"],
        }
        for s in TOOL_SCHEMAS
    ]

    messages: list[dict] = [{"role": "user", "content": initial_message}]

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=config.model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        assistant_content: list[Any] = []
        tool_results: list[dict] = []
        final_text = ""

        for block in response.content:
            assistant_content.append(block)
            if block.type == "text":
                final_text = block.text
            elif block.type == "tool_use":
                name = block.name
                args = block.input or {}
                console.print(f"  [dim]→ {name}({_fmt_args(args)})[/dim]")
                output = run_tool(name, args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn" or not tool_results:
            return final_text

        messages.append({"role": "user", "content": tool_results})

    return "[에이전트] 최대 턴 수에 도달했습니다."


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        parts.append(f"{k}={v!r}")
    return ", ".join(parts)


# ── 공개 진입점 ──

_OPENAI_PROVIDERS = {"openai", "openai-compat", "vllm", "lm-studio"}
_ANTHROPIC_PROVIDERS = {"anthropic"}
_NO_TOOL_PROVIDERS = {"ollama"}


def run_agent(config: AgentConfig, target: str, namespace: str, since: str) -> str:
    """에이전트 루프를 실행하고 최종 리포트 문자열을 반환한다."""
    provider = config.provider

    if provider in _NO_TOOL_PROVIDERS:
        raise RuntimeError(
            f"'{provider}' provider는 tool use를 지원하지 않습니다.\n"
            "에이전트 모드는 openai / anthropic / openai-compat 에서만 사용 가능합니다.\n"
            "예: sre-agent inspect my-pod --agent --provider anthropic"
        )

    initial_message = (
        f"다음 Kubernetes 리소스를 조사해 장애 원인을 파악해라.\n"
        f"대상: {target}\n"
        f"namespace: {namespace}\n"
        f"로그 기간: {since}\n\n"
        f"kubectl tool을 사용해 직접 조사하고 최종 리포트를 작성해라."
    )

    console.print("\n[bold]Agent 모드[/bold] — LLM이 직접 kubectl을 실행합니다.\n")

    if provider in _OPENAI_PROVIDERS:
        return _run_openai_loop(config, initial_message)
    if provider in _ANTHROPIC_PROVIDERS:
        return _run_anthropic_loop(config, initial_message)

    raise RuntimeError(f"지원하지 않는 provider: {provider}")
