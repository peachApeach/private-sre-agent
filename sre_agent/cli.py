import json
import sys
from collections import Counter

import typer
from rich.console import Console
from rich.table import Table

from sre_agent.analyzers.log_patterns import analyze_log_patterns
from sre_agent.harness.redactor import redact

from sre_agent.llm.ollama import summarize_with_ollama
from sre_agent.report.diagnosis import build_diagnosis_report

from sre_agent.collectors.kubernetes import collect_pod_logs
from sre_agent.report.diagnosis import build_diagnosis_report
from sre_agent.llm.ollama import summarize_with_ollama

from sre_agent.collectors.kubernetes import (
    collect_namespace_events,
    collect_pod_describe,
    collect_pod_json,
    collect_pod_logs,
    parse_pod_json,
)
from sre_agent.analyzers.pod_state import analyze_pod_state
from sre_agent.analyzers.events import analyze_events

from sre_agent.collectors.kubernetes import (
    collect_deployment_json,
    collect_namespace_events,
    collect_pod_json,
    collect_pod_logs,
    collect_pods_by_selector_json,
    parse_json,
    parse_pod_json,
)
from sre_agent.analyzers.deployment import (
    deployment_selector_to_label_selector,
    summarize_deployment,
)

from sre_agent.llm.providers import summarize_with_provider

app = typer.Typer(help="Private SRE CLI agent")
console = Console()


@app.command()
def analyze(
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Run only local pattern analysis without LLM summary.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print raw JSON result.",
    ),
    model: str = typer.Option(
        "qwen2.5:3b",
        "--model",
        help="Ollama model name.",
    ),
    model_provider: str = typer.Option(
        "ollama",
        "--model-provider",
        help="LLM provider: ollama or openai.",
    ),
    debug_patterns: bool = typer.Option(
        False,
        "--debug-patterns",
        help="Print raw grouped log patterns.",
    ),
):
    raw = sys.stdin.read()

    if not raw.strip():
        console.print("[red]No logs received from stdin.[/red]")
        raise typer.Exit(code=1)

    redacted = redact(raw)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    if json_output:
        console.print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    render_analysis_result(
        result=result,
        no_llm=no_llm,
        model=model,
        debug_patterns=debug_patterns,
    )

@app.command()
def klogs(
    pod: str = typer.Argument(..., help="Pod name."),
    namespace: str = typer.Option(
        "default",
        "--namespace",
        "-n",
        help="Kubernetes namespace.",
    ),
    since: str = typer.Option(
        "30m",
        "--since",
        help="Only return logs newer than a relative duration like 30m, 1h.",
    ),
    container: str | None = typer.Option(
        None,
        "--container",
        "-c",
        help="Container name.",
    ),
    previous: bool = typer.Option(
        False,
        "--previous",
        help="Return previous terminated container logs.",
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Run only local pattern analysis without LLM summary.",
    ),
    model: str = typer.Option(
        "qwen2.5:3b",
        "--model",
        help="Ollama model name.",
    ),
    debug_patterns: bool = typer.Option(
        False,
        "--debug-patterns",
        help="Print raw grouped log patterns.",
    ),
):
    """
    Collect pod logs with kubectl logs and analyze them.
    """
    console.print(
        f"[dim]Collecting logs: pod={pod}, namespace={namespace}, since={since}[/dim]"
    )

    command_result = collect_pod_logs(
        pod=pod,
        namespace=namespace,
        since=since,
        container=container,
        previous=previous,
    )

    if command_result.returncode != 0:
        console.print("[red]kubectl logs failed.[/red]")
        console.print(command_result.stderr)
        raise typer.Exit(code=command_result.returncode)

    redacted = redact(command_result.stdout)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    render_analysis_result(
        result=result,
        no_llm=no_llm,
        model=model,
        debug_patterns=debug_patterns,
    )

def render_analysis_result(
    result: dict,
    no_llm: bool,
    model: str,
    debug_patterns: bool,
):
    console.print("[bold]Private SRE Agent - Log Pattern Analysis[/bold]\n")
    console.print(f"Total lines: [bold]{result['total_lines']}[/bold]")
    console.print(f"Signal lines: [bold]{result['signal_lines']}[/bold]\n")

    if result.get("status") == "ok":
        console.print("[green]No error or warning signals were detected.[/green]")
        console.print("현재 로그에서는 ERROR/WARN/Exception/OOMKilled/CrashLoopBackOff 같은 장애 신호가 발견되지 않았습니다.")
        return

    diagnosis = build_diagnosis_report(result)

    category_table = Table(title="Top issue categories")
    category_table.add_column("#", justify="right")
    category_table.add_column("Count", justify="right")
    category_table.add_column("Issue")

    for idx, item in enumerate(result.get("top_categories", []), start=1):
        category_table.add_row(
            str(idx),
            str(item["count"]),
            item["category"],
        )

    console.print(category_table)

    console.print("\n[bold]Deterministic SRE Report[/bold]\n")
    console.print(f"[bold]요약[/bold]\n{diagnosis['summary']}\n")

    signal_table = Table(title="Prioritized signals")
    signal_table.add_column("#", justify="right")
    signal_table.add_column("Severity")
    signal_table.add_column("Count", justify="right")
    signal_table.add_column("Signal")

    for idx, item in enumerate(diagnosis["top_signals"], start=1):
        signal_table.add_row(
            str(idx),
            item["severity"],
            str(item["count"]),
            item["category"],
        )

    console.print(signal_table)

    unknown_signals = diagnosis.get("unknown_signals", [])
    if unknown_signals:
        unknown_table = Table(title="Unknown issue patterns")
        unknown_table.add_column("#", justify="right")
        unknown_table.add_column("Count", justify="right")
        unknown_table.add_column("Category")
        unknown_table.add_column("Sample")

        for idx, item in enumerate(unknown_signals, start=1):
            samples = item.get("samples", [])
            sample = samples[0] if samples else ""
            unknown_table.add_row(
                str(idx),
                str(item["count"]),
                item["category"],
                sample,
            )

        console.print(unknown_table)

    console.print("\n[bold]원인 후보[/bold]")
    for item in diagnosis["cause_candidates"]:
        console.print(f"- {item}")

    console.print("\n[bold]다음 확인 액션[/bold]")
    for item in diagnosis["checks"]:
        console.print(f"- {item}")

    console.print("\n[bold]주의[/bold]")
    for item in diagnosis["cautions"]:
        console.print(f"- {item}")

    if debug_patterns:
        detail_table = Table(title="Raw grouped log patterns")
        detail_table.add_column("#", justify="right")
        detail_table.add_column("Count", justify="right")
        detail_table.add_column("Pattern")

        for idx, item in enumerate(result["top_patterns"], start=1):
            detail_table.add_row(
                str(idx),
                str(item["count"]),
                item["pattern"],
            )

        console.print(detail_table)

    if not no_llm:
        console.print("\n[bold]AI Summary[/bold]\n")
        try:
            summary = summarize_with_provider(
                diagnosis,
                provider=model_provider,
                model=model,
            )
            console.print(summary)
        except Exception as exc:
            console.print("[red]Failed to generate LLM summary.[/red]")
            console.print(f"[yellow]{exc}[/yellow]")
            console.print("\nTip: Ollama가 실행 중인지 확인해봐: [bold]ollama list[/bold]")

@app.command()
def inspect(
    pod: str = typer.Argument(..., help="Pod name."),
    namespace: str = typer.Option(
        "default",
        "--namespace",
        "-n",
        help="Kubernetes namespace.",
    ),
    since: str = typer.Option(
        "30m",
        "--since",
        help="Only return logs newer than a relative duration like 30m, 1h.",
    ),
    container: str | None = typer.Option(
        None,
        "--container",
        "-c",
        help="Container name.",
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Run only local analysis without LLM summary.",
    ),
    model: str = typer.Option(
        "qwen2.5:3b",
        "--model",
        help="Ollama model name.",
    ),
    debug_patterns: bool = typer.Option(
        False,
        "--debug-patterns",
        help="Print raw grouped log patterns.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print detailed pod status, events, and full log analysis.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print result as JSON.",
    ),
):
    """
    Inspect pod status, events, current logs, and previous logs.
    """
    if not json_output:
        console.print(
            f"[dim]Pod 점검 중: pod={pod}, namespace={namespace}, since={since}[/dim]"
        )

    pod_json_result = collect_pod_json(pod=pod, namespace=namespace)
    if pod_json_result.returncode != 0:
        console.print("[red]kubectl get pod failed.[/red]")
        console.print(pod_json_result.stderr)
        raise typer.Exit(code=pod_json_result.returncode)

    pod_json = parse_pod_json(pod_json_result.stdout)
    pod_state = analyze_pod_state(pod_json)

    events_result = collect_namespace_events(namespace=namespace)
    events_analysis = {}
    if events_result.returncode == 0:
        events_analysis = analyze_events(events_result.stdout, pod=pod)
    else:
        events_analysis = {
            "matched_event_count": 0,
            "events": [],
            "signals": [],
            "error": events_result.stderr,
        }

    logs_result = collect_pod_logs(
        pod=pod,
        namespace=namespace,
        since=since,
        container=container,
        previous=False,
    )

    if logs_result.returncode != 0:
        console.print("[yellow]kubectl logs failed; continuing with pod status/events only.[/yellow]")
        console.print(logs_result.stderr)

    current_logs = logs_result.stdout if logs_result.returncode == 0 else ""

    previous_logs_result = collect_pod_logs(
        pod=pod,
        namespace=namespace,
        since=since,
        container=container,
        previous=True,
    )

    if previous_logs_result.returncode != 0 and previous_logs_result.stderr.strip():
        console.print("[dim]kubectl logs --previous not available.[/dim]")

    previous_logs = (
        previous_logs_result.stdout
        if previous_logs_result.returncode == 0
        else ""
    )

    combined_logs = "\n".join(
        part for part in [current_logs, previous_logs] if part.strip()
    )

    redacted = redact(combined_logs)
    lines = redacted.splitlines()
    result = analyze_log_patterns(lines)

    pod_inspect_result = {
        "target": {
            "kind": "Pod",
            "name": pod,
            "namespace": namespace,
            "since": since,
            "container": container,
        },
        "pod": pod_state,
        "events": events_analysis,
        "logs": {
            "previous_logs_available": bool(previous_logs.strip()),
            "current_logs_available": bool(current_logs.strip()),
        },
        "log_analysis": result,
    }

    if result is None:
        result = {
            "total_lines": len(lines),
            "signal_lines": 0,
            "status": "ok",
            "message": "No error or warning signals were detected.",
            "top_categories": [],
            "top_known_categories": [],
            "top_unknown_categories": [],
            "top_patterns": [],
            "samples": [],
        }

    if json_output:
        console.print_json(
            json.dumps(
                pod_inspect_result,
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if verbose:
        render_pod_inspect_summary(
            pod_state=pod_state,
            events_analysis=events_analysis,
            previous_logs_available=bool(previous_logs.strip()),
        )

        render_inspect_diagnosis(
            pod_state=pod_state,
            events_analysis=events_analysis,
            log_result=result,
            previous_logs_available=bool(previous_logs.strip()),
        )

        render_analysis_result(
            result=result,
            no_llm=no_llm,
            model=model,
            debug_patterns=debug_patterns,
        )
    else:
        render_compact_inspect_result(
            pod_state=pod_state,
            events_analysis=events_analysis,
            log_result=result,
            previous_logs_available=bool(previous_logs.strip()),
        )

@app.command("inspect-deploy")
def inspect_deploy(
    deployment: str = typer.Argument(..., help="Deployment name."),
    namespace: str = typer.Option(
        "default",
        "--namespace",
        "-n",
        help="Kubernetes namespace.",
    ),
    since: str = typer.Option(
        "30m",
        "--since",
        help="Only return logs newer than a relative duration like 30m, 1h.",
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Run only local analysis without LLM summary.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print detailed analysis.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print result as JSON.",
    ),
):

    if not json_output:
        console.print(
            f"[dim]Deployment 점검 중: deploy={deployment}, namespace={namespace}, since={since}[/dim]"
        )

    deploy_result = collect_deployment_json(
        deployment=deployment,
        namespace=namespace,
    )

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

    pods_result = collect_pods_by_selector_json(
        selector=selector,
        namespace=namespace,
    )

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

    events_result = collect_namespace_events(namespace=namespace)

    namespace_events_text = ""
    if events_result.returncode == 0:
        namespace_events_text = events_result.stdout
    else:
        console.print("[yellow]kubectl get events failed; continuing without events.[/yellow]")
        console.print(events_result.stderr)    

    pods_json = parse_json(pods_result.stdout)
    pod_items = pods_json.get("items", [])

    all_logs = []
    pod_summaries = []
    
    all_event_signals = []

    for pod_item in pod_items:
        pod_name = pod_item.get("metadata", {}).get("name")

        pod_events_analysis = analyze_events(
            namespace_events_text,
            pod=pod_name,
        ) if namespace_events_text else {
            "matched_event_count": 0,
            "events": [],
            "signals": [],
        }

        pod_state = analyze_pod_state(pod_item)

        pod_events_analysis = analyze_events(
            namespace_events_text,
            pod=pod_name,
        ) if namespace_events_text else {
            "matched_event_count": 0,
            "events": [],
            "signals": [],
        }

        all_event_signals.extend(pod_events_analysis.get("signals", []))

        containers = pod_state.get("containers", [])
        ready_values = [item.get("ready") for item in containers]
        ready = all(ready_values) if ready_values else None

        reason = None
        for container in containers:
            reason = container.get("current_reason") or container.get("last_reason")
            if reason:
                break

        logs_result = collect_pod_logs(
            pod=pod_name,
            namespace=namespace,
            since=since,
            previous=False,
        )

        if logs_result.returncode == 0 and logs_result.stdout.strip():
            all_logs.append(logs_result.stdout)

        previous_result = collect_pod_logs(
            pod=pod_name,
            namespace=namespace,
            since=since,
            previous=True,
        )

        previous_logs_available = (
            previous_result.returncode == 0
            and bool(previous_result.stdout.strip())
        )

        if previous_logs_available:
            all_logs.append(previous_result.stdout)

        pod_summaries.append(
            {
                "name": pod_name,
                "ready": ready,
                "restart_count": pod_state.get("total_restart_count", 0),
                "reason": reason,
                "previous_logs_available": previous_logs_available,
                "event_signals": pod_events_analysis.get("signals", []),
            }
        )

    combined_logs = "\n".join(all_logs)
    redacted = redact(combined_logs)
    lines = redacted.splitlines()
    combined_log_result = analyze_log_patterns(lines)

    combined_log_result = analyze_log_patterns(lines)
    deploy_inspect_result = {
        "target": {
            "kind": "Deployment",
            "name": deployment,
            "namespace": namespace,
            "since": since,
        },
        "deployment": deploy_summary,
        "pods": pod_summaries,
        "events": {
            "signals": all_event_signals,
        },
        "log_analysis": combined_log_result,
    }

    if json_output:
        console.print_json(
            json.dumps(
                deploy_inspect_result,
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if verbose:
        render_compact_deploy_result(
            deploy_summary=deploy_summary,
            pod_summaries=pod_summaries,
            combined_log_result=combined_log_result,
            event_signals=all_event_signals,
        )

        render_analysis_result(
            result=combined_log_result,
            no_llm=no_llm,
            model="qwen2.5:3b",
            debug_patterns=False,
        )
    else:
        render_compact_deploy_result(
            deploy_summary=deploy_summary,
            pod_summaries=pod_summaries,
            combined_log_result=combined_log_result,
            event_signals=all_event_signals,
        )

def render_pod_inspect_summary(
    pod_state: dict,
    events_analysis: dict,
    previous_logs_available: bool,
):
    console.print("\n[bold]Pod Inspect Summary[/bold]\n")

    table = Table(title="Pod status")
    table.add_column("Field")
    table.add_column("Value")

    table.add_row("Name", str(pod_state.get("name")))
    table.add_row("Namespace", str(pod_state.get("namespace")))
    table.add_row("Phase", str(pod_state.get("phase")))
    table.add_row("Node", str(pod_state.get("node_name")))
    table.add_row("Pod IP", str(pod_state.get("pod_ip")))
    table.add_row("Restart Count", str(pod_state.get("total_restart_count")))
    table.add_row("Previous Logs", "available" if previous_logs_available else "not available")

    console.print(table)

    containers = pod_state.get("containers", [])
    if containers:
        container_table = Table(title="Containers")
        container_table.add_column("Name")
        container_table.add_column("Ready")
        container_table.add_column("Restarts", justify="right")
        container_table.add_column("Current Reason")
        container_table.add_column("Last Reason")

        for item in containers:
            container_table.add_row(
                str(item.get("name")),
                str(item.get("ready")),
                str(item.get("restart_count")),
                str(item.get("current_reason")),
                str(item.get("last_reason")),
            )

        console.print(container_table)

    pod_signals = pod_state.get("signals", [])
    event_signals = events_analysis.get("signals", [])

    if pod_signals or event_signals:
        signal_table = Table(title="Kubernetes state/event signals")
        signal_table.add_column("#", justify="right")
        signal_table.add_column("Severity")
        signal_table.add_column("Category")
        signal_table.add_column("Message")

        idx = 1
        for signal in pod_signals + event_signals:
            signal_table.add_row(
                str(idx),
                str(signal.get("severity")),
                str(signal.get("category")),
                str(signal.get("message")),
            )
            idx += 1

        console.print(signal_table)

def render_inspect_diagnosis(
    pod_state: dict,
    events_analysis: dict,
    log_result: dict,
    previous_logs_available: bool,
):
    console.print("\n[bold]Inspect Diagnosis[/bold]\n")

    restart_count = pod_state.get("total_restart_count", 0)
    phase = pod_state.get("phase")
    pod_name = pod_state.get("name")

    categories = [
        item.get("category")
        for item in log_result.get("top_categories", [])
    ]

    event_signals = events_analysis.get("signals", [])
    has_backoff_event = any(
        "BackOff" in signal.get("category", "")
        for signal in event_signals
    )

    summary_parts = []

    if restart_count > 0:
        summary_parts.append(
            f"{pod_name}는 현재 {restart_count}회 재시작된 상태입니다"
        )

    if has_backoff_event:
        summary_parts.append(
            "Kubernetes BackOff 이벤트가 관측되어 컨테이너가 반복 실패 후 재시작 대기 중일 가능성이 있습니다"
        )

    if previous_logs_available:
        summary_parts.append(
            "previous logs가 있어 직전 실패 컨테이너 로그를 분석에 포함했습니다"
        )

    if "Java OutOfMemoryError" in categories:
        summary_parts.append(
            "로그에서 Java OutOfMemoryError가 확인되어 JVM 메모리 문제 가능성이 있습니다"
        )

    if "DB connection pool timeout" in categories:
        summary_parts.append(
            "DB connection pool timeout도 함께 확인되어 DB connection 고갈 또는 connection leak 가능성을 확인해야 합니다"
        )

    if not summary_parts:
        summary_parts.append(
            f"{pod_name}의 phase는 {phase}이며, 명확한 Kubernetes 상태 이상은 제한적으로만 확인됩니다"
        )

    console.print("요약")
    console.print("- " + "\n- ".join(summary_parts))

    console.print("\n우선 확인 액션")
    if restart_count > 0:
        console.print("- kubectl logs --previous 결과를 우선 확인")
        console.print("- 컨테이너 exit code, termination reason 확인")
    if "Java OutOfMemoryError" in categories:
        console.print("- memory request/limit 및 JVM -Xmx/MaxRAMPercentage 확인")
        console.print("- OOM 직전 heap/GC 로그 또는 메모리 사용 추이 확인")
    if "DB connection pool timeout" in categories:
        console.print("- HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 확인")
        console.print("- DB active/max connection, slow query, lock wait 확인")
    if has_backoff_event:
        console.print("- liveness/readiness/startup probe 실패 여부 확인")
        console.print("- 최근 rollout/config/secret 변경 여부 확인")

def render_inspect_diagnosis(
    pod_state: dict,
    events_analysis: dict,
    log_result: dict,
    previous_logs_available: bool,
):
    console.print("\n[bold]Inspect Diagnosis[/bold]\n")

    restart_count = pod_state.get("total_restart_count", 0)
    phase = pod_state.get("phase")
    pod_name = pod_state.get("name")

    categories = [
        item.get("category")
        for item in log_result.get("top_categories", [])
    ]

    event_signals = events_analysis.get("signals", [])
    has_backoff_event = any(
        "BackOff" in signal.get("category", "")
        for signal in event_signals
    )

    has_crashloop_event = any(
        "CrashLoopBackOff" in signal.get("category", "")
        for signal in event_signals
    )

    has_image_pull_error = any(
        "image pull" in signal.get("category", "").lower()
        for signal in event_signals
    )

    summary_parts = []

    if restart_count > 0:
        summary_parts.append(
            f"{pod_name}는 현재 {restart_count}회 재시작된 상태입니다."
        )

    if has_backoff_event:
        summary_parts.append(
            "Kubernetes BackOff 이벤트가 관측되어 컨테이너가 반복 실패 후 재시작 대기 중일 가능성이 있습니다."
        )

    if has_crashloop_event:
        summary_parts.append(
            "CrashLoopBackOff 이벤트가 관측되어 컨테이너가 지속적으로 실패하고 있을 가능성이 높습니다."
        )

    if has_image_pull_error:
        summary_parts.append(
            "이미지 pull 관련 이벤트가 관측되어 이미지 이름, 태그, registry 인증 정보를 확인해야 합니다."
        )

    if previous_logs_available:
        summary_parts.append(
            "previous logs가 있어 직전 실패 컨테이너 로그를 분석에 포함했습니다."
        )

    if "Java OutOfMemoryError" in categories:
        summary_parts.append(
            "로그에서 Java OutOfMemoryError가 확인되어 JVM 메모리 문제 가능성이 있습니다."
        )

    if "Kubernetes OOMKilled" in categories:
        summary_parts.append(
            "Kubernetes OOMKilled 신호가 확인되어 컨테이너가 memory limit을 초과했을 가능성이 있습니다."
        )

    if "DB connection pool timeout" in categories:
        summary_parts.append(
            "DB connection pool timeout도 함께 확인되어 DB connection 고갈 또는 connection leak 가능성을 확인해야 합니다."
        )

    if "Redis connection failure" in categories:
        summary_parts.append(
            "Redis 연결 실패가 확인되어 Redis service, endpoint, network policy를 확인해야 합니다."
        )

    if not summary_parts:
        summary_parts.append(
            f"{pod_name}의 phase는 {phase}이며, 현재 수집된 정보에서는 명확한 Kubernetes 상태 이상이 제한적으로만 확인됩니다."
        )

    console.print("[bold]요약[/bold]")
    for item in summary_parts:
        console.print(f"- {item}")

    console.print("\n[bold]우선 확인 액션[/bold]")

    actions = []

    if restart_count > 0:
        actions.extend(
            [
                "kubectl logs --previous 결과를 우선 확인",
                "컨테이너 exit code, termination reason 확인",
            ]
        )

    if "Java OutOfMemoryError" in categories or "Kubernetes OOMKilled" in categories:
        actions.extend(
            [
                "memory request/limit 및 JVM -Xmx/MaxRAMPercentage 확인",
                "OOM 직전 heap/GC 로그 또는 메모리 사용 추이 확인",
            ]
        )

    if "DB connection pool timeout" in categories:
        actions.extend(
            [
                "HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 확인",
                "DB active/max connection, slow query, lock wait 확인",
            ]
        )

    if "Redis connection failure" in categories:
        actions.extend(
            [
                "Redis pod/service/endpoints 상태 확인",
                "pod에서 Redis DNS resolve 및 port 연결 가능 여부 확인",
            ]
        )

    if has_backoff_event or has_crashloop_event:
        actions.extend(
            [
                "liveness/readiness/startup probe 실패 여부 확인",
                "최근 rollout/config/secret 변경 여부 확인",
            ]
        )

    if has_image_pull_error:
        actions.extend(
            [
                "image name/tag 오타 확인",
                "imagePullSecret 및 registry 접근 권한 확인",
            ]
        )

    if not actions:
        actions.append("추가 로그, events, metrics를 함께 확인")

    for action in _dedupe_strings(actions):
        console.print(f"- {action}")


def _dedupe_strings(items: list[str]) -> list[str]:
    seen = set()
    result = []

    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result

def render_compact_inspect_result(
    pod_state: dict,
    events_analysis: dict,
    log_result: dict,
    previous_logs_available: bool,
):
    pod_name = pod_state.get("name")
    namespace = pod_state.get("namespace")
    phase = pod_state.get("phase")
    restart_count = pod_state.get("total_restart_count", 0)

    containers = pod_state.get("containers", [])
    ready_values = [item.get("ready") for item in containers]
    ready = all(ready_values) if ready_values else None

    console.print("[bold]Private SRE Agent[/bold]\n")
    console.print(
        f"대상: [bold]pod/{pod_name}[/bold] 네임스페이스=[bold]{namespace}[/bold]"
    )
    console.print(
        f"상태: {phase} | Ready={ready} | 재시작={restart_count}회 | "
        f"이전 로그={'있음' if previous_logs_available else '없음'}"
    )

    categories = log_result.get("top_categories", [])
    event_signals = events_analysis.get("signals", [])

    has_backoff_event = any(
        "BackOff" in signal.get("category", "")
        for signal in event_signals
    )

    console.print("\n[bold]진단 요약[/bold]")

    diagnosis_lines = []

    if restart_count > 0:
        diagnosis_lines.append(f"Pod가 {restart_count}회 재시작되었습니다.")

    if not ready:
        diagnosis_lines.append("Pod가 Ready 상태가 아닙니다.")

    if has_backoff_event:
        diagnosis_lines.append("Kubernetes BackOff 이벤트가 감지되었습니다.")

    if previous_logs_available:
        diagnosis_lines.append("이전 컨테이너 로그를 함께 분석했습니다.")

    category_names = [item.get("category") for item in categories]

    if "Java OutOfMemoryError" in category_names:
        diagnosis_lines.append("Java OutOfMemoryError가 감지되었습니다.")

    if "Kubernetes OOMKilled" in category_names:
        diagnosis_lines.append("Kubernetes OOMKilled 신호가 감지되었습니다.")

    if "DB connection pool timeout" in category_names:
        diagnosis_lines.append("DB connection pool timeout이 감지되었습니다.")

    if "Redis connection failure" in category_names:
        diagnosis_lines.append("Redis 연결 실패가 감지되었습니다.")

    unknowns = log_result.get("top_unknown_categories", [])
    if unknowns:
        diagnosis_lines.append(f"아직 룰에 등록되지 않은 unknown 패턴 {len(unknowns)}종이 감지되었습니다.")

    if not diagnosis_lines:
        diagnosis_lines.append("수집된 로그와 이벤트에서 뚜렷한 장애 신호는 발견되지 않았습니다.")

    for line in diagnosis_lines:
        console.print(f"- {line}")

    console.print("\n[bold]주요 신호[/bold]")

    combined_signals = []

    severity_label_map = {
        "high": "높음",
        "medium": "중간",
        "low": "낮음",
        "unknown": "알수없음",
    }

    for item in categories[:5]:
        severity = item.get("severity") or "unknown"
        severity_label = severity_label_map.get(severity, severity)

        console.print(
            f"- [{severity_label}] {item.get('category')}: {item.get('count')}건"
        )

    for signal in event_signals[:3]:
        combined_signals.append(
            {
                "severity": signal.get("severity", "unknown"),
                "name": signal.get("category"),
                "count": 1,
            }
        )

    if combined_signals:
        for item in combined_signals[:6]:
            console.print(
                f"- [{item['severity']}] {item['name']}: {item['count']}건"
            )
    else:
        console.print("- 없음")

    console.print("\n[bold]다음 확인 액션[/bold]")

    actions = []

    if previous_logs_available or restart_count > 0:
        actions.append("이전 컨테이너 로그와 종료 사유를 확인하세요.")

    if "Java OutOfMemoryError" in category_names or "Kubernetes OOMKilled" in category_names:
        actions.append("memory request/limit 및 JVM -Xmx/MaxRAMPercentage 설정을 확인하세요.")

    if "DB connection pool timeout" in category_names:
        actions.append("HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 설정을 확인하세요.")

    if "Redis connection failure" in category_names:
        actions.append("Redis service/endpoints 및 pod 내부 DNS 해석 여부를 확인하세요.")

    if has_backoff_event:
        actions.append("liveness/readiness/startup probe와 최근 rollout/config/secret 변경 여부를 확인하세요.")

    if unknowns:
        actions.append("unknown 패턴을 검토하고 필요하면 새 룰로 추가하세요.")

    if not actions:
        actions.append("문제가 지속되면 metrics, events, 최근 배포 이력을 함께 확인하세요.")

    for action in _dedupe_strings(actions)[:6]:
        console.print(f"- {action}")

def render_compact_deploy_result(
    deploy_summary: dict,
    pod_summaries: list[dict],
    combined_log_result: dict,
    event_signals: list[dict] | None = None,
):
    event_signals = event_signals or []
    console.print("[bold]Private SRE Agent[/bold]\n")

    event_counter = Counter(
        signal.get("category", "Unknown Kubernetes event")
        for signal in event_signals
    )

    console.print(
        f"대상: [bold]deploy/{deploy_summary.get('name')}[/bold] "
        f"네임스페이스=[bold]{deploy_summary.get('namespace')}[/bold]"
    )

    console.print(
        "상태: "
        f"replicas={deploy_summary.get('replicas')} | "
        f"ready={deploy_summary.get('ready_replicas', 0)} | "
        f"available={deploy_summary.get('available_replicas', 0)} | "
        f"updated={deploy_summary.get('updated_replicas', 0)}"
    )

    not_ready = [
        item for item in pod_summaries
        if item.get("ready") is False
    ]

    total_restarts = sum(
        item.get("restart_count", 0)
        for item in pod_summaries
    )

    console.print("\n[bold]진단 요약[/bold]")

    replicas = deploy_summary.get("replicas") or 0
    ready_replicas = deploy_summary.get("ready_replicas") or 0
    available_replicas = deploy_summary.get("available_replicas") or 0

    if ready_replicas < replicas:
        console.print(
            f"- desired replicas({replicas}) 대비 ready pod({ready_replicas})가 부족합니다."
        )

    if available_replicas < replicas:
        console.print(
            f"- available replicas({available_replicas})가 desired replicas({replicas})보다 적습니다."
        )

    if not_ready:
        console.print(f"- Ready가 아닌 pod가 {len(not_ready)}개 있습니다.")

    if total_restarts > 0:
        console.print(f"- 관련 pod들의 총 재시작 횟수는 {total_restarts}회입니다.")

    categories = combined_log_result.get("top_categories", [])
    category_names = [item.get("category") for item in categories]

    if "Java OutOfMemoryError" in category_names:
        console.print("- Java OutOfMemoryError가 감지되었습니다.")

    if "DB connection pool timeout" in category_names:
        console.print("- DB connection pool timeout이 감지되었습니다.")

    if "Redis connection failure" in category_names:
        console.print("- Redis 연결 실패가 감지되었습니다.")

    unknowns = combined_log_result.get("top_unknown_categories", [])
    if unknowns:
        console.print(f"- Unknown 패턴 {len(unknowns)}종이 감지되었습니다.")

    if not not_ready and total_restarts == 0 and not categories:
        console.print("- 수집된 범위에서는 뚜렷한 장애 신호가 발견되지 않았습니다.")

    console.print("\n[bold]Pod 요약[/bold]")
    for item in pod_summaries:
        console.print(
            f"- {item.get('name')} | Ready={item.get('ready')} | "
            f"Restarts={item.get('restart_count')} | "
            f"Reason={item.get('reason')} | "
            f"이전로그={'있음' if item.get('previous_logs_available') else '없음'}"
        )

    if event_counter:
        severity_by_category = {}

        for signal in event_signals:
            category = signal.get("category", "Unknown Kubernetes event")
            severity = signal.get("severity", "unknown")
            current = severity_by_category.get(category)

            if current is None:
                severity_by_category[category] = severity
            elif current != "high" and severity == "high":
                severity_by_category[category] = severity

        severity_label_map = {
            "high": "높음",
            "medium": "중간",
            "low": "낮음",
            "unknown": "알수없음",
        }

        console.print("\n[bold]Kubernetes 이벤트[/bold]")

        for category, count in event_counter.most_common(5):
            severity = severity_by_category.get(category, "unknown")
            severity_label = severity_label_map.get(severity, severity)
            console.print(f"- [{severity_label}] {category}: {count}건")

    console.print("\n[bold]주요 신호[/bold]")
    if categories:
        for item in categories[:5]:
            severity = item.get("severity") or "unknown"
            severity_label = severity_label_map.get(severity, severity)
            console.print(
                f"- [{severity_label}] {item.get('category')}: {item.get('count')}건"
            )
    else:
        console.print("- 없음")

    console.print("\n[bold]다음 확인 액션[/bold]")
    actions = []

    if not_ready or total_restarts > 0:
        actions.append("문제 pod를 대상으로 sre-agent inspect <pod>를 실행하세요.")

    if "Java OutOfMemoryError" in category_names:
        actions.append("memory request/limit 및 JVM -Xmx/MaxRAMPercentage 설정을 확인하세요.")

    if "DB connection pool timeout" in category_names:
        actions.append("HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 설정을 확인하세요.")

    if "Redis connection failure" in category_names:
        actions.append("Redis service/endpoints 및 pod 내부 DNS 해석 여부를 확인하세요.")

    actions.append("최근 rollout/config/secret 변경 여부를 확인하세요.")

    for action in _dedupe_strings(actions):
        console.print(f"- {action}")

if __name__ == "__main__":
    app()