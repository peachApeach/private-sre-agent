from sre_agent.report.diagnosis import build_diagnosis_report


def _make_analysis(categories: list[dict]) -> dict:
    return {"top_categories": categories, "top_unknown_categories": []}


def _cat(name: str, severity: str = "high", count: int = 5) -> dict:
    return {
        "category": name,
        "count": count,
        "severity": severity,
        "meaning": "",
        "possible_causes": ["cause A", "cause B"],
        "checks": ["check 1", "check 2"],
    }


def test_db_timeout_in_summary():
    analysis = _make_analysis([_cat("DB connection pool timeout")])
    report = build_diagnosis_report(analysis)
    assert "DB connection pool timeout" in report["summary"]


def test_redis_failure_in_summary():
    analysis = _make_analysis([_cat("Redis connection failure")])
    report = build_diagnosis_report(analysis)
    assert "Redis" in report["summary"]


def test_java_oom_and_k8s_oom_combined():
    analysis = _make_analysis([
        _cat("Java OutOfMemoryError"),
        _cat("Kubernetes OOMKilled"),
    ])
    report = build_diagnosis_report(analysis)
    assert "OutOfMemoryError" in report["summary"]
    assert "OOMKilled" in report["summary"]


def test_no_hardcoded_service_names():
    analysis = _make_analysis([_cat("Downstream failure from payment-api")])
    report = build_diagnosis_report(analysis)
    assert "payment-api" not in report["summary"]
    assert "order-api" not in report["summary"]


def test_cause_candidates_deduped():
    analysis = _make_analysis([_cat("DB connection pool timeout"), _cat("Redis connection failure")])
    report = build_diagnosis_report(analysis)
    causes = report["cause_candidates"]
    assert len(causes) == len(set(causes))


def test_empty_categories():
    analysis = _make_analysis([])
    report = build_diagnosis_report(analysis)
    assert isinstance(report["summary"], str)
    assert len(report["summary"]) > 0
