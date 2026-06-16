import json

import typer
from rich.console import Console

from sre_agent.analyzers.events import analyze_events
from sre_agent.analyzers.log_patterns import analyze_log_patterns
from sre_agent.analyzers.pod_state import analyze_pod_state
from sre_agent.collectors.kubernetes import (
    collect_namespace_events,
    collect_pod_json,
    collect_pod_logs,
    parse_pod_json,
)
from sre_agent.config import AgentConfig
from sre_agent.harness.redactor import redact
from sre_agent.render.rich_renderer import (
    render_analysis_result,
    render_compact_inspect_result,
    render_inspect_diagnosis,
    render_pod_inspect_summary,
)

console = Console()


def cmd_inspect(
    pod: str,
    namespace: str,
    since: str,
    container: str | None,
    no_llm: bool,
    provider: str | None,
    model: str | None,
    debug_patterns: bool,
    verbose: bool,
    json_output: bool,
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

    if not json_output:
        console.print(f"[dim]Pod 점검 중: pod={pod}, namespace={namespace}, since={since}[/dim]")

    pod_json_result = collect_pod_json(pod=pod, namespace=namespace)
    if pod_json_result.returncode != 0:
        console.print("[red]kubectl get pod failed.[/red]")
        console.print(pod_json_result.stderr)
        raise typer.Exit(code=pod_json_result.returncode)

    pod_json = parse_pod_json(pod_json_result.stdout)
    pod_state = analyze_pod_state(pod_json)

    events_result = collect_namespace_events(namespace=namespace)
    if events_result.returncode == 0:
        events_analysis = analyze_events(events_result.stdout, pod=pod)
    else:
        events_analysis = {"matched_event_count": 0, "events": [], "signals": [], "error": events_result.stderr}

    logs_result = collect_pod_logs(pod=pod, namespace=namespace, since=since, container=container, previous=False)
    if logs_result.returncode != 0:
        console.print("[yellow]kubectl logs failed; continuing with pod status/events only.[/yellow]")
        console.print(logs_result.stderr)
    current_logs = logs_result.stdout if logs_result.returncode == 0 else ""

    prev_result = collect_pod_logs(pod=pod, namespace=namespace, since=since, container=container, previous=True)
    if prev_result.returncode != 0 and prev_result.stderr.strip():
        console.print("[dim]kubectl logs --previous not available.[/dim]")
    previous_logs = prev_result.stdout if prev_result.returncode == 0 else ""

    combined_logs = "\n".join(part for part in [current_logs, previous_logs] if part.strip())
    redacted = redact(combined_logs)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    pod_inspect_result = {
        "target": {"kind": "Pod", "name": pod, "namespace": namespace, "since": since, "container": container},
        "pod": pod_state,
        "events": events_analysis,
        "logs": {
            "previous_logs_available": bool(previous_logs.strip()),
            "current_logs_available": bool(current_logs.strip()),
        },
        "log_analysis": result,
    }

    if json_output:
        console.print_json(json.dumps(pod_inspect_result, ensure_ascii=False, indent=2))
        return

    config = AgentConfig(provider=provider, model=model)
    previous_logs_available = bool(previous_logs.strip())

    if verbose:
        render_pod_inspect_summary(
            pod_state=pod_state,
            events_analysis=events_analysis,
            previous_logs_available=previous_logs_available,
        )
        render_inspect_diagnosis(
            pod_state=pod_state,
            events_analysis=events_analysis,
            log_result=result,
            previous_logs_available=previous_logs_available,
        )
        render_analysis_result(result=result, no_llm=no_llm, config=config, debug_patterns=debug_patterns, raw_logs=redacted)
    else:
        render_compact_inspect_result(
            pod_state=pod_state,
            events_analysis=events_analysis,
            log_result=result,
            previous_logs_available=previous_logs_available,
        )
        if not no_llm and redacted.strip():
            from sre_agent.report.diagnosis import build_diagnosis_report
            from sre_agent.render.rich_renderer import _build_rule_context, run_chat_loop
            from rich.markdown import Markdown
            console.print("\n[bold]AI 분석[/bold]\n")
            try:
                diagnosis = build_diagnosis_report(result)
                rule_context = _build_rule_context(diagnosis)
                llm_analysis = config.analyze_logs(logs=redacted, context=rule_context)
                console.print(Markdown(llm_analysis))
                run_chat_loop(initial_analysis=llm_analysis, config=config)
            except Exception as exc:
                console.print(f"[red]LLM 분석 실패: {exc}[/red]")
