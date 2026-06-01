import json

from sre_agent.harness.command_runner import CommandResult, run_command


def collect_pod_logs(
    pod: str,
    namespace: str = "default",
    since: str = "30m",
    container: str | None = None,
    previous: bool = False,
) -> CommandResult:
    command = [
        "kubectl",
        "logs",
        pod,
        "-n",
        namespace,
        f"--since={since}",
    ]

    if container:
        command.extend(["-c", container])

    if previous:
        command.append("--previous")

    return run_command(command, timeout=90)


def collect_pod_json(
    pod: str,
    namespace: str = "default",
) -> CommandResult:
    command = [
        "kubectl",
        "get",
        "pod",
        pod,
        "-n",
        namespace,
        "-o",
        "json",
    ]
    return run_command(command, timeout=30)


def collect_pod_describe(
    pod: str,
    namespace: str = "default",
) -> CommandResult:
    command = [
        "kubectl",
        "describe",
        "pod",
        pod,
        "-n",
        namespace,
    ]
    return run_command(command, timeout=30)


def collect_namespace_events(
    namespace: str = "default",
) -> CommandResult:
    command = [
        "kubectl",
        "get",
        "events",
        "-n",
        namespace,
        "--sort-by=.lastTimestamp",
    ]
    return run_command(command, timeout=30)


def parse_pod_json(stdout: str) -> dict:
    if not stdout.strip():
        return {}
    return json.loads(stdout)

def collect_deployment_json(
    deployment: str,
    namespace: str = "default",
) -> CommandResult:
    command = [
        "kubectl",
        "get",
        "deploy",
        deployment,
        "-n",
        namespace,
        "-o",
        "json",
    ]
    return run_command(command, timeout=30)


def collect_pods_by_selector_json(
    selector: str,
    namespace: str = "default",
) -> CommandResult:
    command = [
        "kubectl",
        "get",
        "pods",
        "-n",
        namespace,
        "-l",
        selector,
        "-o",
        "json",
    ]
    return run_command(command, timeout=30)


def parse_json(stdout: str) -> dict:
    if not stdout.strip():
        return {}
    return json.loads(stdout)