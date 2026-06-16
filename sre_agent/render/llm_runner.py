"""LLM 분석 실행 + 대화 루프. 렌더링과 분리."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

console = Console()

_CHAT_SYSTEM_PROMPT = (
    "You are an SRE expert. Respond ONLY in Korean (한국어). Do not use English in your response.\n\n"
    "너는 SRE 전문가다. 반드시 한국어로만 답해라. 영어 응답은 절대 금지.\n"
    "아래 로그 분석 결과를 바탕으로 사용자의 후속 질문에 답해라. "
    "로그에 없는 내용은 추측임을 명시해라. 짧고 실무적으로 답해라.\n\n"
)


def run_llm_analysis_and_chat(raw_logs: str, log_result: dict, config) -> None:
    """rule engine 결과 + 원본 로그를 LLM에 넘겨 분석 출력 후 대화 루프 진입."""
    if not raw_logs.strip():
        console.print("[yellow]로그가 없어 LLM 분석을 건너뜁니다.[/yellow]")
        return
    from sre_agent.report.diagnosis import build_diagnosis_report
    from sre_agent.render.rich_renderer import _build_rule_context
    console.print("\n[bold]AI 분석[/bold]\n")
    try:
        diagnosis = build_diagnosis_report(log_result)
        rule_context = _build_rule_context(diagnosis)
        llm_analysis = config.analyze_logs(logs=raw_logs, context=rule_context)
        console.print(Markdown(llm_analysis))
        run_chat_loop(initial_analysis=llm_analysis, config=config)
    except Exception as exc:
        console.print(f"[red]LLM 분석 실패: {exc}[/red]")


def run_chat_loop(initial_analysis: str, config) -> None:
    """LLM 분석 결과를 시작점으로 대화 루프를 실행한다."""
    console.print("\n[bold dim]─── 대화 모드 (quit 또는 exit 로 종료) ───[/bold dim]\n")

    system_prompt = _CHAT_SYSTEM_PROMPT + f"[초기 분석 결과]\n{initial_analysis}"
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]대화 종료.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "종료", "q"}:
            console.print("[dim]대화 종료.[/dim]")
            break

        messages.append({"role": "user", "content": user_input})
        console.print("[dim]...[/dim]")
        try:
            reply = config.chat(messages)
        except Exception as exc:
            console.print(f"[red]LLM 오류: {exc}[/red]")
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": reply})
        console.print()
        console.print(Markdown(reply))
        console.print()
