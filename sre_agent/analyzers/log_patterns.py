import re
from collections import Counter

from sre_agent.analyzers.advice import ISSUE_ADVICE


SIGNAL_KEYWORDS = [
    "ERROR",
    "WARN",
    "EXCEPTION",
    "TIMEOUT",
    "FAILED",
    "OOMKILLED",
    "OOMKILLING",
    "CRASHLOOPBACKOFF",
    "BACKOFF",
    "CONNECTION IS NOT AVAILABLE",
    "CONNECTION REFUSED",
]


def is_signal_line(line: str) -> bool:
    upper = line.upper()
    return any(keyword in upper for keyword in SIGNAL_KEYWORDS)


def classify_pattern(line: str) -> dict:
    upper = line.upper()

    if "SQLTRANSIENTCONNECTIONEXCEPTION" in upper or "CONNECTION IS NOT AVAILABLE" in upper:
        return {
            "category": "DB connection pool timeout",
            "known": True,
            "confidence": "high",
        }

    if "EXTERNAL PAYMENT GATEWAY RESPONSE DELAYED" in upper:
        return {
            "category": "External payment gateway delay",
            "known": True,
            "confidence": "high",
        }

    if "REDISCONNECTIONFAILUREEXCEPTION" in upper or "UNABLE TO CONNECT TO REDIS" in upper:
        return {
            "category": "Redis connection failure",
            "known": True,
            "confidence": "high",
        }

    if "OUTOFMEMORYERROR" in upper or "JAVA HEAP SPACE" in upper:
        return {
            "category": "Java OutOfMemoryError",
            "known": True,
            "confidence": "high",
        }

    if "OOMKILLED" in upper or "OOMKILLING" in upper:
        return {
            "category": "Kubernetes OOMKilled",
            "known": True,
            "confidence": "high",
        }

    if "CRASHLOOPBACKOFF" in upper:
        return {
            "category": "Kubernetes CrashLoopBackOff",
            "known": True,
            "confidence": "high",
        }

    if "BACK-OFF RESTARTING FAILED CONTAINER" in upper or "BACKOFF" in upper:
        return {
            "category": "Kubernetes BackOff restarting container",
            "known": True,
            "confidence": "high",
        }

    if "PAYMENT-API RETURNED HTTP" in upper:
        return {
            "category": "Downstream failure from payment-api",
            "known": True,
            "confidence": "medium",
        }
    
    if "ORDER QUEUED BECAUSE PAYMENT CONFIRMATION IS DELAYED" in upper:
        return {
            "category": "Order queued due to payment delay",
            "known": True,
            "confidence": "medium",
        }

    return {
        "category": infer_fallback_category(line),
        "known": False,
        "confidence": "low",
    }


def infer_fallback_category(line: str) -> str:
    upper = line.upper()

    if "AUTH" in upper or "JWT" in upper or "TOKEN" in upper:
        return "Unknown auth-related error"

    if "TIMEOUT" in upper or "TIMED OUT" in upper:
        return "Unknown timeout error"

    if "CONNECTION" in upper or "CONNECT" in upper:
        return "Unknown connection error"

    if "MEMORY" in upper or "HEAP" in upper:
        return "Unknown memory error"

    if "HTTP 5" in upper or "STATUS=5" in upper or "STATUS=<NUM>" in upper:
        return "Unknown HTTP 5xx error"

    if "CERTIFICATE" in upper or "TLS" in upper or "SSL" in upper:
        return "Unknown TLS/certificate error"

    if "DISK" in upper or "NO SPACE LEFT" in upper:
        return "Unknown disk/storage error"

    return "Unknown warning/error"


def normalize_line(line: str) -> str:
    line = re.sub(r"\b\d{4}-\d{2}-\d{2}T[^\s]+", "<timestamp>", line)

    line = re.sub(r"trace_id=[^\s]+", "trace_id=<trace_id>", line)
    line = re.sub(r"request_id=[^\s]+", "request_id=<request_id>", line)
    line = re.sub(r"\breq-\d+\b", "req-<num>", line)

    line = re.sub(
        r"pod=([a-zA-Z0-9-]+)-[0-9a-f]{6,}-[a-z0-9]{4,}",
        r"pod=\1-<pod_id>",
        line,
    )
    line = re.sub(
        r"pod ([a-zA-Z0-9-]+)-[0-9a-f]{6,}-[a-z0-9]{4,}",
        r"pod \1-<pod_id>",
        line,
    )

    line = re.sub(r"user_id=\d+", "user_id=<user_id>", line)
    line = re.sub(r"customer_email=[^\s]+", "customer_email=<email>", line)
    line = re.sub(r"customer_phone=[^\s]+", "customer_phone=<phone>", line)
    line = re.sub(r"authorization=\"Bearer [^\"]+\"", "authorization=\"Bearer <token>\"", line)

    line = re.sub(r"latency_ms=\d+", "latency_ms=<num>", line)
    line = re.sub(r"status=\d+", "status=<num>", line)
    line = re.sub(r"retry_count=\d+", "retry_count=<num>", line)
    line = re.sub(r"version=\d+\.\d+\.\d+-\d+", "version=<version>", line)
    line = re.sub(r"HikariPool-\d+", "HikariPool-<num>", line)
    line = re.sub(r"after \d+ms", "after <num>ms", line)
    # host:port 패턴 치환.
    # 파일경로(.java:42, .kt:88) 및 소스 위치 키워드(line:, at:, row:, col:)는 제외
    _PORT_SKIP = re.compile(r"(?:\.[a-zA-Z]{1,4}|line|at|row|col)$", re.IGNORECASE)
    def _replace_port(m: re.Match) -> str:
        prefix = m.group(1)
        if _PORT_SKIP.search(prefix):
            return m.group(0)
        return prefix + ":<port>"
    line = re.sub(r"([a-zA-Z0-9\-_\.]+):(\d{2,5})\b", _replace_port, line)

    line = re.sub(r"\b[0-9a-fA-F]{6,}\b", "<hex>", line)
    line = re.sub(r"\b\d+\b", "<num>", line)

    return line


def analyze_log_patterns(lines: list[str], top_n: int = 10) -> dict:
    signal_lines = [line for line in lines if is_signal_line(line)]

    if not signal_lines:
        return {
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

    classifications = [classify_pattern(line) for line in signal_lines]

    category_counter = Counter(
        item["category"] for item in classifications
    )

    known_counter = Counter(
        item["category"] for item in classifications if item.get("known") is True
    )

    unknown_counter = Counter(
        item["category"] for item in classifications if item.get("known") is False
    )

    unknown_samples_by_category = {}

    for line, item in zip(signal_lines, classifications):
        if item.get("known") is False:
            category = item["category"]
            unknown_samples_by_category.setdefault(category, [])
            if len(unknown_samples_by_category[category]) < 3:
                unknown_samples_by_category[category].append(normalize_line(line))

    normalized_lines = [normalize_line(line) for line in signal_lines]
    pattern_counter = Counter(normalized_lines)

    top_categories = []

    for category, count in category_counter.most_common(top_n):
        advice = ISSUE_ADVICE.get(category, {})
        known = any(
            item["category"] == category and item.get("known") is True
            for item in classifications
        )

        top_categories.append(
            {
                "category": category,
                "count": count,
                "known": known,
                "severity": advice.get("severity", "unknown"),
                "meaning": advice.get("meaning", ""),
                "possible_causes": advice.get("possible_causes", []),
                "checks": advice.get("checks", []),
            }
        )

    top_known_categories = [
        {
            "category": category,
            "count": count,
            "severity": ISSUE_ADVICE.get(category, {}).get("severity", "unknown"),
        }
        for category, count in known_counter.most_common(top_n)
    ]

    top_unknown_categories = [
        {
            "category": category,
            "count": count,
            "samples": unknown_samples_by_category.get(category, []),
        }
        for category, count in unknown_counter.most_common(top_n)
    ]

    top_patterns = [
        {
            "pattern": pattern,
            "count": count,
        }
        for pattern, count in pattern_counter.most_common(top_n)
    ]

    return {
        "total_lines": len(lines),
        "signal_lines": len(signal_lines),
        "top_categories": top_categories,
        "top_known_categories": top_known_categories,
        "top_unknown_categories": top_unknown_categories,
        "top_patterns": top_patterns,
        "samples": signal_lines[:10],
    }