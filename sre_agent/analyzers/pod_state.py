def analyze_pod_state(pod_json: dict) -> dict:
    metadata = pod_json.get("metadata", {})
    status = pod_json.get("status", {})
    spec = pod_json.get("spec", {})

    container_statuses = status.get("containerStatuses", []) or []

    containers = []
    total_restart_count = 0
    reasons = []

    for item in container_statuses:
        name = item.get("name")
        restart_count = item.get("restartCount", 0)
        total_restart_count += restart_count

        state = item.get("state", {})
        last_state = item.get("lastState", {})

        current_reason = _extract_state_reason(state)
        last_reason = _extract_state_reason(last_state)

        if current_reason:
            reasons.append(current_reason)
        if last_reason:
            reasons.append(last_reason)

        containers.append(
            {
                "name": name,
                "ready": item.get("ready"),
                "restart_count": restart_count,
                "current_reason": current_reason,
                "last_reason": last_reason,
                "image": item.get("image"),
            }
        )

    phase = status.get("phase", "Unknown")

    signals = []

    if total_restart_count > 0:
        signals.append(
            {
                "category": "Pod has restarts",
                "severity": "medium",
                "message": f"Pod containers restarted {total_restart_count} times.",
            }
        )

    for reason in set(reasons):
        upper = reason.upper()
        severity = "medium"

        if "OOMKILLED" in upper:
            severity = "high"
        elif "CRASHLOOPBACKOFF" in upper:
            severity = "high"
        elif "ERROR" in upper or "FAILED" in upper:
            severity = "high"

        signals.append(
            {
                "category": f"Pod state reason: {reason}",
                "severity": severity,
                "message": f"Container state reason detected: {reason}",
            }
        )

    return {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "node_name": spec.get("nodeName"),
        "phase": phase,
        "pod_ip": status.get("podIP"),
        "host_ip": status.get("hostIP"),
        "total_restart_count": total_restart_count,
        "containers": containers,
        "signals": signals,
    }


def _extract_state_reason(state: dict) -> str | None:
    if not state:
        return None

    for _, value in state.items():
        if isinstance(value, dict):
            reason = value.get("reason")
            if reason:
                return reason

    return None