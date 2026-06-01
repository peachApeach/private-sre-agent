IMPORTANT_EVENT_KEYWORDS = [
    "OOMKilled",
    "OOMKilling",
    "BackOff",
    "CrashLoopBackOff",
    "Failed",
    "FailedMount",
    "FailedScheduling",
    "Unhealthy",
    "ErrImagePull",
    "ImagePullBackOff",
    "Killing",
]


def analyze_events(events_text: str, pod: str | None = None, max_events: int = 20) -> dict:
    lines = [line for line in events_text.splitlines() if line.strip()]

    matched = []

    for line in lines:
        if pod and pod not in line:
            continue

        upper = line.upper()
        if any(keyword.upper() in upper for keyword in IMPORTANT_EVENT_KEYWORDS):
            matched.append(line)

    return {
        "matched_event_count": len(matched),
        "events": matched[-max_events:],
        "signals": [_event_to_signal(line) for line in matched[-max_events:]],
    }


def _event_to_signal(line: str) -> dict:
    upper = line.upper()

    severity = "medium"
    category = "Kubernetes warning event"

    if "OOMKILLED" in upper or "OOMKILLING" in upper:
        severity = "high"
        category = "Kubernetes OOM event"
    elif "CRASHLOOPBACKOFF" in upper:
        severity = "high"
        category = "Kubernetes CrashLoopBackOff event"
    elif "IMAGEPULLBACKOFF" in upper or "ERRIMAGEPULL" in upper:
        severity = "high"
        category = "Kubernetes image pull error"
    elif "FAILEDSCHEDULING" in upper:
        severity = "high"
        category = "Kubernetes scheduling failure"
    elif "BACKOFF" in upper:
        severity = "medium"
        category = "Kubernetes BackOff event"
    elif "UNHEALTHY" in upper:
        severity = "medium"
        category = "Kubernetes health check failure"

    return {
        "category": category,
        "severity": severity,
        "message": line,
    }