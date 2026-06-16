import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich.console import Console

from sre_agent.analyzers.deployment import deployment_selector_to_label_selector, summarize_deployment
from sre_agent.analyzers.events import analyze_events
from sre_agent.analyzers.log_patterns import analyze_log_patterns
from sre_agent.analyzers.pod_state import analyze_pod_state
from sre_agent.collectors.kubernetes import (
    collect_deployment_json,
    collect_namespace_events,
    collect_pod_logs,
    collect_pods_by_selector_json,
    parse_json,
)
from sre_agent.config import AgentConfig
from sre_agent.harness.redactor import redact
from sre_agent.render.rich_renderer import render_analysis_result, render_compact_deploy_result

console = Console()


def _collect_pod_logs_parallel(
    pod_name: str,
    namespace: str,
    since: str,
) -> dict:
    """current + previous 로그를 병렬로 수집해 반환한다."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_current = ex.submit(collect_pod_logs, pod_name, namespace, since, None, False)
        fut_prev = ex.submit(collect_pod_logs, pod_name, namespace, since, None, True)
        current_result = fut_current.result()
        prev_result = fut_prev.result()

    current_logs = current_result.stdout if current_result.returncode == 0 else ""
    previous_logs = prev_result.stdout if prev_result.returncode == 0 else ""
    return {
        "current": current_logs,
        "previous": previous_logs,
        "previous_available": bool(previous_logs.strip()),
    }


def cmd_inspect_deploy(
    deployment: str,
    namespace: str,
    since: str,
    no_llm: bool,
    provider: str | None,
    model: str | None,
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
            report = run_agent(config=config, target=f"deploy/{deployment}", namespace=namespace, since=since)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        console.print(Markdown(report))
        run_chat_loop(initial_analysis=report, config=config)
        return

    if not json_output:
        console.print(f"[dim]Deployment 점검 중: deploy={deployment}, namespace={namespace}, since={since}[/dim]")

    deploy_result = collect_deployment_json(deployment=deployment, namespace=namespace)
    if deploy_result.returncode != 0:
        console.print("[red]kubectl get deploy failed.[/red]")
        console.print(deploy_result.stderr)
        raise typer.Exit(code=deploy_result.returncode)

    deploy_json = parse_json(deploy_result.stdout)
    deploy_summary = summarize_deployment(deploy_json)

    selector = deployment_selector_to_label_selector(deploy_json)
    if not selector:
        console.print("[red]Deployment selector를 찾지 못했습니다.[/red]")
        raise typer.Exit(code=1)

    pods_result = collect_pods_by_selector_json(selector=selector, namespace=namespace)
    if pods_result.returncode != 0:
        console.print("[red]kubectl get pods failed.[/red]")
        console.print(pods_result.stderr)
        raise typer.Exit(code=pods_result.returncode)

    events_result = collect_namespace_events(namespace=namespace)
    namespace_events_text = ""
    if events_result.returncode == 0:
        namespace_events_text = events_result.stdout
    else:
        console.print("[yellow]kubectl get events failed; continuing without events.[/yellow]")
        console.print(events_result.stderr)

    pods_json = parse_json(pods_result.stdout)
    pod_items = pods_json.get("items", [])

    # pod별 로그를 병렬 수집 (pod당 current+previous 동시 실행)
    with ThreadPoolExecutor(max_workers=min(len(pod_items), 8)) as executor:
        futures = {
            executor.submit(
                _collect_pod_logs_parallel,
                pod_item.get("metadata", {}).get("name"),
                namespace,
                since,
            ): pod_item
            for pod_item in pod_items
        }
        logs_by_pod: dict[str, dict] = {}
        for fut in as_completed(futures):
            pod_item = futures[fut]
            pod_name = pod_item.get("metadata", {}).get("name")
            logs_by_pod[pod_name] = fut.result()

    all_logs: list[str] = []
    pod_summaries: list[dict] = []
    all_event_signals: list[dict] = []

    for pod_item in pod_items:
        pod_name = pod_item.get("metadata", {}).get("name")
        pod_state = analyze_pod_state(pod_item)

        pod_events_analysis = (
            analyze_events(namespace_events_text, pod=pod_name)
            if namespace_events_text
            else {"matched_event_count": 0, "events": [], "signals": []}
        )
        all_event_signals.extend(pod_events_analysis.get("signals", []))

        containers = pod_state.get("containers", [])
        ready_values = [c.get("ready") for c in containers]
        ready = all(ready_values) if ready_values else None

        reason = None
        for container in containers:
            reason = container.get("current_reason") or container.get("last_reason")
            if reason:
                break

        pod_logs = logs_by_pod.get(pod_name, {})
        if pod_logs.get("current"):
            all_logs.append(pod_logs["current"])
        if pod_logs.get("previous"):
            all_logs.append(pod_logs["previous"])

        pod_summaries.append({
            "name": pod_name,
            "ready": ready,
            "restart_count": pod_state.get("total_restart_count", 0),
            "reason": reason,
            "previous_logs_available": pod_logs.get("previous_available", False),
            "event_signals": pod_events_analysis.get("signals", []),
        })

    combined_logs = "\n".join(all_logs)
    redacted = redact(combined_logs)
    lines = redacted.splitlines()
    combined_log_result = analyze_log_patterns(lines)

    deploy_inspect_result = {
        "target": {"kind": "Deployment", "name": deployment, "namespace": namespace, "since": since},
        "deployment": deploy_summary,
        "pods": pod_summaries,
        "events": {"signals": all_event_signals},
        "log_analysis": combined_log_result,
    }

    if json_output:
        console.print_json(json.dumps(deploy_inspect_result, ensure_ascii=False, indent=2))
        return

    config = AgentConfig(provider=provider, model=model)

    render_compact_deploy_result(
        deploy_summary=deploy_summary,
        pod_summaries=pod_summaries,
        combined_log_result=combined_log_result,
        event_signals=all_event_signals,
    )

    if verbose:
        render_analysis_result(
            result=combined_log_result,
            no_llm=no_llm,
            config=config,
            debug_patterns=False,
            raw_logs=redacted,
        )
    elif not no_llm and redacted.strip():
        from sre_agent.report.diagnosis import build_diagnosis_report
        from sre_agent.render.rich_renderer import _build_rule_context, run_chat_loop
        from rich.markdown import Markdown
        console.print("\n[bold]AI 분석[/bold]\n")
        try:
            diagnosis = build_diagnosis_report(combined_log_result)
            rule_context = _build_rule_context(diagnosis)
            llm_analysis = config.analyze_logs(logs=redacted, context=rule_context)
            console.print(Markdown(llm_analysis))
            run_chat_loop(initial_analysis=llm_analysis, config=config)
        except Exception as exc:
            console.print(f"[red]LLM 분석 실패: {exc}[/red]")
