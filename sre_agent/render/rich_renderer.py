from collections import Counter

from rich.console import Console
from rich.table import Table

console = Console()

_SEVERITY_LABEL = {
    "high": "높음",
    "medium": "중간",
    "low": "낮음",
    "unknown": "알수없음",
}


def _severity(value: str | None) -> str:
    return _SEVERITY_LABEL.get(value or "unknown", value or "unknown")


def _build_rule_context(diagnosis: dict) -> str:
    lines = []
    if diagnosis.get("summary"):
        lines.append(f"요약: {diagnosis['summary']}")
    for sig in diagnosis.get("top_signals", [])[:5]:
        lines.append(f"[{sig.get('severity', '?')}] {sig.get('category')}: {sig.get('count')}건")
    for u in diagnosis.get("unknown_signals", [])[:3]:
        samples = u.get("samples", [])
        sample = f" — 예: {samples[0]}" if samples else ""
        lines.append(f"[unknown] {u.get('category')}: {u.get('count')}건{sample}")
    return "\n".join(lines) if lines else "사전 분석 결과 없음"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def render_analysis_result(
    result: dict,
    no_llm: bool,
    config,
    debug_patterns: bool,
    raw_logs: str = "",
) -> None:
    from sre_agent.report.diagnosis import build_diagnosis_report

    console.print("[bold]Private SRE Agent - Log Pattern Analysis[/bold]\n")
    console.print(f"Total lines: [bold]{result['total_lines']}[/bold]")
    console.print(f"Signal lines: [bold]{result['signal_lines']}[/bold]\n")

    if result.get("status") == "ok":
        console.print("[green]장애 신호가 발견되지 않았습니다.[/green]")
        console.print("ERROR/WARN/Exception/OOMKilled/CrashLoopBackOff 신호 없음.")
        return

    diagnosis = build_diagnosis_report(result)

    category_table = Table(title="Top issue categories")
    category_table.add_column("#", justify="right")
    category_table.add_column("Count", justify="right")
    category_table.add_column("Issue")
    for idx, item in enumerate(result.get("top_categories", []), start=1):
        category_table.add_row(str(idx), str(item["count"]), item["category"])
    console.print(category_table)

    console.print("\n[bold]Deterministic SRE Report[/bold]\n")
    console.print(f"[bold]요약[/bold]\n{diagnosis['summary']}\n")

    signal_table = Table(title="Prioritized signals")
    signal_table.add_column("#", justify="right")
    signal_table.add_column("Severity")
    signal_table.add_column("Count", justify="right")
    signal_table.add_column("Signal")
    for idx, item in enumerate(diagnosis["top_signals"], start=1):
        signal_table.add_row(str(idx), item["severity"], str(item["count"]), item["category"])
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
            unknown_table.add_row(str(idx), str(item["count"]), item["category"], samples[0] if samples else "")
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
            detail_table.add_row(str(idx), str(item["count"]), item["pattern"])
        console.print(detail_table)

    if not no_llm:
        run_llm_analysis_and_chat(raw_logs=raw_logs, log_result=result, config=config)


def render_pod_inspect_summary(
    pod_state: dict,
    events_analysis: dict,
    previous_logs_available: bool,
) -> None:
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
        ct = Table(title="Containers")
        ct.add_column("Name")
        ct.add_column("Ready")
        ct.add_column("Restarts", justify="right")
        ct.add_column("Current Reason")
        ct.add_column("Last Reason")
        for item in containers:
            ct.add_row(
                str(item.get("name")),
                str(item.get("ready")),
                str(item.get("restart_count")),
                str(item.get("current_reason")),
                str(item.get("last_reason")),
            )
        console.print(ct)

    pod_signals = pod_state.get("signals", [])
    event_signals = events_analysis.get("signals", [])
    if pod_signals or event_signals:
        st = Table(title="Kubernetes state/event signals")
        st.add_column("#", justify="right")
        st.add_column("Severity")
        st.add_column("Category")
        st.add_column("Message")
        for idx, signal in enumerate(pod_signals + event_signals, start=1):
            st.add_row(str(idx), str(signal.get("severity")), str(signal.get("category")), str(signal.get("message")))
        console.print(st)


def render_inspect_diagnosis(
    pod_state: dict,
    events_analysis: dict,
    log_result: dict,
    previous_logs_available: bool,
) -> None:
    console.print("\n[bold]Inspect Diagnosis[/bold]\n")

    restart_count = pod_state.get("total_restart_count", 0)
    phase = pod_state.get("phase")
    pod_name = pod_state.get("name")
    categories = [item.get("category") for item in log_result.get("top_categories", [])]
    event_signals = events_analysis.get("signals", [])

    has_backoff = any("BackOff" in s.get("category", "") for s in event_signals)
    has_crashloop = any("CrashLoopBackOff" in s.get("category", "") for s in event_signals)
    has_image_pull = any("image pull" in s.get("category", "").lower() for s in event_signals)

    summary_parts = []
    if restart_count > 0:
        summary_parts.append(f"{pod_name}는 현재 {restart_count}회 재시작된 상태입니다.")
    if has_backoff:
        summary_parts.append("Kubernetes BackOff 이벤트가 관측되어 컨테이너가 반복 실패 후 재시작 대기 중일 가능성이 있습니다.")
    if has_crashloop:
        summary_parts.append("CrashLoopBackOff 이벤트가 관측되어 컨테이너가 지속적으로 실패하고 있을 가능성이 높습니다.")
    if has_image_pull:
        summary_parts.append("이미지 pull 관련 이벤트가 관측되어 이미지 이름, 태그, registry 인증 정보를 확인해야 합니다.")
    if previous_logs_available:
        summary_parts.append("previous logs가 있어 직전 실패 컨테이너 로그를 분석에 포함했습니다.")
    if "Java OutOfMemoryError" in categories:
        summary_parts.append("로그에서 Java OutOfMemoryError가 확인되어 JVM 메모리 문제 가능성이 있습니다.")
    if "Kubernetes OOMKilled" in categories:
        summary_parts.append("Kubernetes OOMKilled 신호가 확인되어 컨테이너가 memory limit을 초과했을 가능성이 있습니다.")
    if "DB connection pool timeout" in categories:
        summary_parts.append("DB connection pool timeout이 확인되어 DB connection 고갈 또는 leak 가능성을 확인해야 합니다.")
    if "Redis connection failure" in categories:
        summary_parts.append("Redis 연결 실패가 확인되어 Redis service, endpoint, network policy를 확인해야 합니다.")
    if not summary_parts:
        summary_parts.append(f"{pod_name}의 phase는 {phase}이며, 현재 수집된 정보에서는 명확한 이상이 제한적으로만 확인됩니다.")

    console.print("[bold]요약[/bold]")
    for item in summary_parts:
        console.print(f"- {item}")

    actions = []
    if restart_count > 0:
        actions += ["kubectl logs --previous 결과를 우선 확인", "컨테이너 exit code, termination reason 확인"]
    if "Java OutOfMemoryError" in categories or "Kubernetes OOMKilled" in categories:
        actions += ["memory request/limit 및 JVM -Xmx/MaxRAMPercentage 확인", "OOM 직전 heap/GC 로그 또는 메모리 사용 추이 확인"]
    if "DB connection pool timeout" in categories:
        actions += ["HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 확인", "DB active/max connection, slow query, lock wait 확인"]
    if "Redis connection failure" in categories:
        actions += ["Redis pod/service/endpoints 상태 확인", "pod에서 Redis DNS resolve 및 port 연결 가능 여부 확인"]
    if has_backoff or has_crashloop:
        actions += ["liveness/readiness/startup probe 실패 여부 확인", "최근 rollout/config/secret 변경 여부 확인"]
    if has_image_pull:
        actions += ["image name/tag 오타 확인", "imagePullSecret 및 registry 접근 권한 확인"]
    if not actions:
        actions.append("추가 로그, events, metrics를 함께 확인")

    console.print("\n[bold]우선 확인 액션[/bold]")
    for action in _dedupe(actions):
        console.print(f"- {action}")


def render_compact_inspect_result(
    pod_state: dict,
    events_analysis: dict,
    log_result: dict,
    previous_logs_available: bool,
) -> None:
    pod_name = pod_state.get("name")
    namespace = pod_state.get("namespace")
    phase = pod_state.get("phase")
    restart_count = pod_state.get("total_restart_count", 0)

    containers = pod_state.get("containers", [])
    ready_values = [item.get("ready") for item in containers]
    ready = all(ready_values) if ready_values else None

    console.print("[bold]Private SRE Agent[/bold]\n")
    console.print(f"대상: [bold]pod/{pod_name}[/bold] 네임스페이스=[bold]{namespace}[/bold]")
    console.print(
        f"상태: {phase} | Ready={ready} | 재시작={restart_count}회 | "
        f"이전 로그={'있음' if previous_logs_available else '없음'}"
    )

    categories = log_result.get("top_categories", [])
    category_names = [item.get("category") for item in categories]
    event_signals = events_analysis.get("signals", [])
    has_backoff = any("BackOff" in s.get("category", "") for s in event_signals)
    unknowns = log_result.get("top_unknown_categories", [])

    console.print("\n[bold]진단 요약[/bold]")
    diagnosis_lines = []
    if restart_count > 0:
        diagnosis_lines.append(f"Pod가 {restart_count}회 재시작되었습니다.")
    if not ready:
        diagnosis_lines.append("Pod가 Ready 상태가 아닙니다.")
    if has_backoff:
        diagnosis_lines.append("Kubernetes BackOff 이벤트가 감지되었습니다.")
    if previous_logs_available:
        diagnosis_lines.append("이전 컨테이너 로그를 함께 분석했습니다.")
    if "Java OutOfMemoryError" in category_names:
        diagnosis_lines.append("Java OutOfMemoryError가 감지되었습니다.")
    if "Kubernetes OOMKilled" in category_names:
        diagnosis_lines.append("Kubernetes OOMKilled 신호가 감지되었습니다.")
    if "DB connection pool timeout" in category_names:
        diagnosis_lines.append("DB connection pool timeout이 감지되었습니다.")
    if "Redis connection failure" in category_names:
        diagnosis_lines.append("Redis 연결 실패가 감지되었습니다.")
    if unknowns:
        diagnosis_lines.append(f"아직 룰에 등록되지 않은 unknown 패턴 {len(unknowns)}종이 감지되었습니다.")
    if not diagnosis_lines:
        diagnosis_lines.append("수집된 로그와 이벤트에서 뚜렷한 장애 신호는 발견되지 않았습니다.")
    for line in diagnosis_lines:
        console.print(f"- {line}")

    console.print("\n[bold]주요 신호[/bold]")
    for item in categories[:5]:
        console.print(f"- [{_severity(item.get('severity'))}] {item.get('category')}: {item.get('count')}건")
    for signal in event_signals[:3]:
        console.print(f"- [{_severity(signal.get('severity'))}] {signal.get('category')}: 1건")
    if not categories and not event_signals:
        console.print("- 없음")

    actions = []
    if previous_logs_available or restart_count > 0:
        actions.append("이전 컨테이너 로그와 종료 사유를 확인하세요.")
    if "Java OutOfMemoryError" in category_names or "Kubernetes OOMKilled" in category_names:
        actions.append("memory request/limit 및 JVM -Xmx/MaxRAMPercentage 설정을 확인하세요.")
    if "DB connection pool timeout" in category_names:
        actions.append("HikariCP maximumPoolSize, connectionTimeout, leakDetectionThreshold 설정을 확인하세요.")
    if "Redis connection failure" in category_names:
        actions.append("Redis service/endpoints 및 pod 내부 DNS 해석 여부를 확인하세요.")
    if has_backoff:
        actions.append("liveness/readiness/startup probe와 최근 rollout/config/secret 변경 여부를 확인하세요.")
    if unknowns:
        actions.append("unknown 패턴을 검토하고 필요하면 새 룰로 추가하세요.")
    if not actions:
        actions.append("문제가 지속되면 metrics, events, 최근 배포 이력을 함께 확인하세요.")

    console.print("\n[bold]다음 확인 액션[/bold]")
    for action in _dedupe(actions)[:6]:
        console.print(f"- {action}")


def render_compact_deploy_result(
    deploy_summary: dict,
    pod_summaries: list[dict],
    combined_log_result: dict,
    event_signals: list[dict] | None = None,
) -> None:
    event_signals = event_signals or []

    console.print("[bold]Private SRE Agent[/bold]\n")
    console.print(
        f"대상: [bold]deploy/{deploy_summary.get('name')}[/bold] "
        f"네임스페이스=[bold]{deploy_summary.get('namespace')}[/bold]"
    )
    console.print(
        f"상태: replicas={deploy_summary.get('replicas')} | "
        f"ready={deploy_summary.get('ready_replicas', 0)} | "
        f"available={deploy_summary.get('available_replicas', 0)} | "
        f"updated={deploy_summary.get('updated_replicas', 0)}"
    )

    not_ready = [item for item in pod_summaries if item.get("ready") is False]
    total_restarts = sum(item.get("restart_count", 0) for item in pod_summaries)
    categories = combined_log_result.get("top_categories", [])
    category_names = [item.get("category") for item in categories]
    unknowns = combined_log_result.get("top_unknown_categories", [])

    replicas = deploy_summary.get("replicas") or 0
    ready_replicas = deploy_summary.get("ready_replicas") or 0
    available_replicas = deploy_summary.get("available_replicas") or 0

    console.print("\n[bold]진단 요약[/bold]")
    if ready_replicas < replicas:
        console.print(f"- desired replicas({replicas}) 대비 ready pod({ready_replicas})가 부족합니다.")
    if available_replicas < replicas:
        console.print(f"- available replicas({available_replicas})가 desired replicas({replicas})보다 적습니다.")
    if not_ready:
        console.print(f"- Ready가 아닌 pod가 {len(not_ready)}개 있습니다.")
    if total_restarts > 0:
        console.print(f"- 관련 pod들의 총 재시작 횟수는 {total_restarts}회입니다.")
    if "Java OutOfMemoryError" in category_names:
        console.print("- Java OutOfMemoryError가 감지되었습니다.")
    if "DB connection pool timeout" in category_names:
        console.print("- DB connection pool timeout이 감지되었습니다.")
    if "Redis connection failure" in category_names:
        console.print("- Redis 연결 실패가 감지되었습니다.")
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

    if event_signals:
        event_counter = Counter(s.get("category", "Unknown Kubernetes event") for s in event_signals)
        severity_by_category: dict[str, str] = {}
        for signal in event_signals:
            cat = signal.get("category", "Unknown Kubernetes event")
            sev = signal.get("severity", "unknown")
            current = severity_by_category.get(cat)
            if current is None or (current != "high" and sev == "high"):
                severity_by_category[cat] = sev

        console.print("\n[bold]Kubernetes 이벤트[/bold]")
        for category, count in event_counter.most_common(5):
            sev = severity_by_category.get(category, "unknown")
            console.print(f"- [{_severity(sev)}] {category}: {count}건")

    console.print("\n[bold]주요 신호[/bold]")
    if categories:
        for item in categories[:5]:
            console.print(f"- [{_severity(item.get('severity'))}] {item.get('category')}: {item.get('count')}건")
    else:
        console.print("- 없음")

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

    console.print("\n[bold]다음 확인 액션[/bold]")
    for action in _dedupe(actions):
        console.print(f"- {action}")


def run_llm_analysis_and_chat(raw_logs: str, log_result: dict, config) -> None:
    from sre_agent.render.llm_runner import run_llm_analysis_and_chat as _run
    _run(raw_logs=raw_logs, log_result=log_result, config=config)


def run_chat_loop(initial_analysis: str, config) -> None:
    from sre_agent.render.llm_runner import run_chat_loop as _run
    _run(initial_analysis=initial_analysis, config=config)
