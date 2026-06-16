"""kubectl tool 정의 — LLM에 넘기는 JSON schema + 실행 함수."""
from __future__ import annotations

from sre_agent.collectors.kubernetes import (
    collect_deployment_json,
    collect_namespace_events,
    collect_pod_json,
    collect_pod_logs,
    parse_json,
    parse_pod_json,
)
from sre_agent.harness.redactor import redact

# ── tool schema (OpenAI / Anthropic 공통 형식으로 변환은 각 provider가 담당) ──

TOOL_SCHEMAS = [
    {
        "name": "get_pod_logs",
        "description": (
            "kubectl logs로 Pod 로그를 수집한다. "
            "current(현재 실행 중) 또는 previous(직전 종료) 컨테이너 로그를 선택할 수 있다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pod": {"type": "string", "description": "Pod 이름"},
                "namespace": {"type": "string", "description": "네임스페이스 (기본: default)"},
                "since": {"type": "string", "description": "로그 기간 (예: 30m, 1h). 기본: 30m"},
                "container": {"type": "string", "description": "컨테이너 이름 (생략 시 첫 번째 컨테이너)"},
                "previous": {"type": "boolean", "description": "true이면 직전 종료 컨테이너 로그 조회"},
            },
            "required": ["pod"],
        },
    },
    {
        "name": "get_pod_status",
        "description": "kubectl get pod -o json으로 Pod 상태(phase, restartCount, containerStatuses 등)를 조회한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "pod": {"type": "string", "description": "Pod 이름"},
                "namespace": {"type": "string", "description": "네임스페이스 (기본: default)"},
            },
            "required": ["pod"],
        },
    },
    {
        "name": "get_events",
        "description": "kubectl get events로 namespace 이벤트를 조회한다. BackOff, OOMKilled, ImagePullBackOff 등 감지에 유용하다.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "네임스페이스 (기본: default)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_deployment",
        "description": "kubectl get deploy -o json으로 Deployment 상태(replicas, conditions 등)를 조회한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "deployment": {"type": "string", "description": "Deployment 이름"},
                "namespace": {"type": "string", "description": "네임스페이스 (기본: default)"},
            },
            "required": ["deployment"],
        },
    },
]


# ── tool 실행 ──

MAX_OUTPUT_CHARS = 8_000


def run_tool(name: str, arguments: dict) -> str:
    """tool 이름과 인수를 받아 실행하고 문자열 결과를 반환한다."""
    try:
        if name == "get_pod_logs":
            return _get_pod_logs(**arguments)
        if name == "get_pod_status":
            return _get_pod_status(**arguments)
        if name == "get_events":
            return _get_events(**arguments)
        if name == "get_deployment":
            return _get_deployment(**arguments)
        return f"[오류] 알 수 없는 tool: {name}"
    except Exception as exc:
        return f"[오류] {name} 실행 실패: {exc}"


def _get_pod_logs(
    pod: str,
    namespace: str = "default",
    since: str = "30m",
    container: str | None = None,
    previous: bool = False,
) -> str:
    result = collect_pod_logs(pod=pod, namespace=namespace, since=since, container=container, previous=previous)
    if result.returncode != 0:
        return f"[kubectl 오류] {result.stderr.strip()}"
    text = redact(result.stdout)
    if not text.strip():
        return "[로그 없음]"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[-MAX_OUTPUT_CHARS:]
        text = f"[앞부분 생략, 마지막 {MAX_OUTPUT_CHARS}자]\n" + text
    return text


def _get_pod_status(pod: str, namespace: str = "default") -> str:
    import json
    result = collect_pod_json(pod=pod, namespace=namespace)
    if result.returncode != 0:
        return f"[kubectl 오류] {result.stderr.strip()}"
    pod_json = parse_pod_json(result.stdout)
    # 필요한 필드만 추출해서 토큰 절약
    status = pod_json.get("status", {})
    summary = {
        "phase": status.get("phase"),
        "conditions": [
            {"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason")}
            for c in status.get("conditions", [])
        ],
        "containerStatuses": [
            {
                "name": c.get("name"),
                "ready": c.get("ready"),
                "restartCount": c.get("restartCount"),
                "state": c.get("state"),
                "lastState": c.get("lastState"),
            }
            for c in status.get("containerStatuses", [])
        ],
        "initContainerStatuses": [
            {
                "name": c.get("name"),
                "ready": c.get("ready"),
                "restartCount": c.get("restartCount"),
                "state": c.get("state"),
            }
            for c in status.get("initContainerStatuses", [])
        ],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def _get_events(namespace: str = "default") -> str:
    result = collect_namespace_events(namespace=namespace)
    if result.returncode != 0:
        return f"[kubectl 오류] {result.stderr.strip()}"
    text = result.stdout
    if not text.strip():
        return "[이벤트 없음]"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[-MAX_OUTPUT_CHARS:]
        text = f"[앞부분 생략]\n" + text
    return text


def _get_deployment(deployment: str, namespace: str = "default") -> str:
    import json
    result = collect_deployment_json(deployment=deployment, namespace=namespace)
    if result.returncode != 0:
        return f"[kubectl 오류] {result.stderr.strip()}"
    deploy_json = parse_json(result.stdout)
    status = deploy_json.get("status", {})
    spec = deploy_json.get("spec", {})
    summary = {
        "name": deploy_json.get("metadata", {}).get("name"),
        "namespace": deploy_json.get("metadata", {}).get("namespace"),
        "replicas": spec.get("replicas"),
        "readyReplicas": status.get("readyReplicas"),
        "availableReplicas": status.get("availableReplicas"),
        "updatedReplicas": status.get("updatedReplicas"),
        "conditions": [
            {"type": c.get("type"), "status": c.get("status"), "message": c.get("message")}
            for c in status.get("conditions", [])
        ],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)
