import json
import sys

import typer
from rich.console import Console

from sre_agent.analyzers.log_patterns import analyze_log_patterns
from sre_agent.config import AgentConfig
from sre_agent.harness.redactor import redact
from sre_agent.render.rich_renderer import render_analysis_result

console = Console()


def cmd_analyze(
    no_llm: bool,
    json_output: bool,
    provider: str | None,
    model: str | None,
    debug_patterns: bool,
    file: str | None = None,
) -> None:
    if file:
        from pathlib import Path
        path = Path(file)
        if not path.exists():
            console.print(f"[red]파일을 찾을 수 없습니다: {file}[/red]")
            raise typer.Exit(code=1)
        raw = path.read_text(errors="replace")
    else:
        if sys.stdin.isatty():
            console.print("[red]로그 파일 경로를 지정하거나 stdin으로 입력해주세요.[/red]")
            console.print("예: sre-agent analyze app.log")
            console.print("예: cat app.log | sre-agent analyze")
            raise typer.Exit(code=1)
        raw = sys.stdin.read()

    if not raw.strip():
        console.print("[red]로그가 비어 있습니다.[/red]")
        raise typer.Exit(code=1)

    redacted = redact(raw)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    if json_output:
        console.print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    config = AgentConfig(provider=provider, model=model)
    render_analysis_result(result=result, no_llm=no_llm, config=config, debug_patterns=debug_patterns, raw_logs=redacted)
