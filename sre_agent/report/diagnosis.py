def build_diagnosis_report(analysis: dict) -> dict:
    categories = analysis.get("top_categories", [])
    unknown_signals = analysis.get("top_unknown_categories", [])

    high_signals = [
        item for item in categories
        if item.get("severity") == "high"
    ]

    cat_set = {item["category"] for item in categories}
    summary_parts = []

    if "DB connection pool timeout" in cat_set:
        summary_parts.append("DB connection pool timeout이 가장 많이 관측되었습니다")
    if "Redis connection failure" in cat_set:
        summary_parts.append("Redis 연결 실패가 함께 발생했습니다")

    has_java_oom = "Java OutOfMemoryError" in cat_set
    has_k8s_oom = "Kubernetes OOMKilled" in cat_set
    has_backoff = "Kubernetes BackOff restarting container" in cat_set

    if has_java_oom and has_k8s_oom:
        summary_parts.append(
            "Java OutOfMemoryError와 Kubernetes OOMKilled 신호가 함께 관측되어 메모리 문제로 인한 컨테이너 종료 가능성이 있습니다"
        )
    elif has_java_oom:
        summary_parts.append(
            "Java OutOfMemoryError 로그가 관측되었지만, Kubernetes OOMKilled 여부는 추가 확인이 필요합니다"
        )
    elif has_k8s_oom:
        summary_parts.append(
            "Kubernetes OOMKilled 신호가 관측되어 컨테이너가 메모리 제한을 초과했을 가능성이 있습니다"
        )

    if has_backoff:
        summary_parts.append(
            "BackOff 신호가 관측되어 컨테이너 재시작 또는 실패 이벤트 여부를 확인해야 합니다"
        )
    if "Downstream failure from payment-api" in cat_set:
        summary_parts.append("downstream 서비스 오류는 upstream API 실패 응답의 영향일 수 있습니다")

    if not summary_parts:
        summary = "주의가 필요한 로그 신호가 관측되었습니다."
    else:
        summary = ". ".join(summary_parts) + "."

    top_signals = [
        {
            "category": item["category"],
            "count": item["count"],
            "severity": item.get("severity", "unknown"),
            "meaning": item.get("meaning", ""),
        }
        for item in categories
    ]

    cause_candidates = []
    checks = []

    for item in categories:
        cause_candidates.extend(item.get("possible_causes", [])[:2])
        checks.extend(item.get("checks", [])[:3])

    cause_candidates = _dedupe(cause_candidates)[:8]
    checks = _dedupe(checks)[:10]

    cautions = [
        "현재 결과는 로그 패턴 기반 분석이므로 특정 원인을 단정할 수 없습니다.",
        "배포 이력, 메트릭, pod 상태, DB/Redis 상태를 함께 확인해야 합니다.",
    ]

    return {
        "summary": summary,
        "high_signal_count": len(high_signals),
        "top_signals": top_signals,
        "cause_candidates": cause_candidates,
        "checks": checks,
        "cautions": cautions,
        "unknown_signals": unknown_signals,
    }


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result