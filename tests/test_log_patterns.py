from sre_agent.analyzers.log_patterns import (
    analyze_log_patterns,
    classify_pattern,
    is_signal_line,
    normalize_line,
)


# ── is_signal_line ──

def test_signal_line_error():
    assert is_signal_line("ERROR: something went wrong") is True


def test_signal_line_warn():
    assert is_signal_line("WARN: low memory") is True


def test_signal_line_oomkilled():
    assert is_signal_line("OOMKilled container") is True


def test_signal_line_normal():
    assert is_signal_line("INFO: application started") is False


# ── classify_pattern ──

def test_classify_db_timeout():
    result = classify_pattern("SQLTransientConnectionException: Connection is not available")
    assert result["category"] == "DB connection pool timeout"
    assert result["known"] is True


def test_classify_redis_failure():
    result = classify_pattern("RedisConnectionFailureException: Unable to connect to Redis")
    assert result["category"] == "Redis connection failure"
    assert result["known"] is True


def test_classify_java_oom():
    result = classify_pattern("java.lang.OutOfMemoryError: Java heap space")
    assert result["category"] == "Java OutOfMemoryError"
    assert result["known"] is True


def test_classify_k8s_oomkilled():
    result = classify_pattern("OOMKilled container exceeded memory limit")
    assert result["category"] == "Kubernetes OOMKilled"
    assert result["known"] is True


def test_classify_crashloop():
    result = classify_pattern("Back-off restarting failed container CrashLoopBackOff")
    assert result["category"] == "Kubernetes CrashLoopBackOff"
    assert result["known"] is True


def test_classify_unknown():
    result = classify_pattern("ERROR: something totally unexpected")
    assert result["known"] is False


# ── normalize_line — port 패턴 ──

def test_normalize_host_port():
    result = normalize_line("connecting to db.internal:5432 failed")
    assert "<port>" in result


def test_normalize_redis_port():
    result = normalize_line("redis://cache:6379 refused")
    assert "<port>" in result


def test_normalize_no_file_path_port():
    result = normalize_line("Exception at MyClass.java:42")
    assert "<port>" not in result


def test_normalize_no_line_number_port():
    result = normalize_line("error at line:123 in module")
    assert "<port>" not in result


def test_normalize_timestamp():
    result = normalize_line("2024-01-15T10:30:00Z ERROR something")
    assert "<timestamp>" in result
    assert "2024" not in result


# ── analyze_log_patterns ──

def test_analyze_empty():
    result = analyze_log_patterns([])
    assert result["status"] == "ok"
    assert result["signal_lines"] == 0


def test_analyze_no_signals():
    lines = ["INFO app started", "INFO connection established"]
    result = analyze_log_patterns(lines)
    assert result["status"] == "ok"


def test_analyze_with_signals():
    lines = [
        "ERROR SQLTransientConnectionException: Connection is not available",
        "ERROR SQLTransientConnectionException: Connection is not available",
        "WARN something else",
    ]
    result = analyze_log_patterns(lines)
    assert result["signal_lines"] == 3
    categories = [c["category"] for c in result["top_categories"]]
    assert "DB connection pool timeout" in categories


def test_analyze_unknown_signal():
    lines = ["ERROR: totally unknown weird error xyz"]
    result = analyze_log_patterns(lines)
    assert result["signal_lines"] == 1
    assert len(result["top_unknown_categories"]) > 0
