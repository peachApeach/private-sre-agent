import typer
from rich.console import Console

from sre_agent.analyzers.log_patterns import analyze_log_patterns
from sre_agent.collectors.kubernetes import collect_pod_logs
from sre_agent.config import AgentConfig
from sre_agent.harness.redactor import redact
from sre_agent.render.rich_renderer import render_analysis_result

console = Console()


def cmd_klogs(
    pod: str,
    namespace: str,
    since: str,
    container: str | None,
    previous: bool,
    no_llm: bool,
    provider: str | None,
    model: str | None,
    debug_patterns: bool,
    agent_mode: bool = False,
) -> None:
    if agent_mode:
        from sre_agent.agent.loop import run_agent
        from sre_agent.render.rich_renderer import run_chat_loop
        from rich.markdown import Markdown
        config = AgentConfig(provider=provider, model=model)
        try:
            report = run_agent(config=config, target=f"pod/{pod}", namespace=namespace, since=since)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        console.print(Markdown(report))
        run_chat_loop(initial_analysis=report, config=config)
        return

    console.print(f"[dim]Collecting logs: pod={pod}, namespace={namespace}, since={since}[/dim]")

    command_result = collect_pod_logs(
        pod=pod, namespace=namespace, since=since, container=container, previous=previous
    )
    if command_result.returncode != 0:
        console.print("[red]kubectl logs failed.[/red]")
        console.print(command_result.stderr)
        raise typer.Exit(code=command_result.returncode)

    redacted = redact(command_result.stdout)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    config = AgentConfig(provider=provider, model=model)
    render_analysis_result(result=result, no_llm=no_llm, config=config, debug_patterns=debug_patterns, raw_logs=redacted)
