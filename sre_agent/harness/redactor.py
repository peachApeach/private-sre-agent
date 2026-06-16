import re

_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"), "<email>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\._\-]+"), "Bearer <token>"),
    # JWT (Bearer 없이 단독으로 로그에 박힌 경우)
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "<jwt>"),
    # AWS access key (총 20자: AKIA + 16자리)
    (re.compile(r"\bAKIA[A-Z0-9]{16}\b"), "<aws-key>"),
    # AWS secret key (40자 base64-like)
    (re.compile(r"(?i)(aws_secret_access_key|aws_secret)\s*=\s*[A-Za-z0-9/+=]{40}"), r"\1=<redacted>"),
    # GCP API key
    (re.compile(r"\bAIza[A-Za-z0-9\-_]{35}\b"), "<gcp-key>"),
    # 시크릿 쿼리 파라미터 / 설정값 (key=value 형태)
    (re.compile(r"(?i)(password|passwd|secret|token|api_?key|apikey|auth)=[^&\s\"']+"), r"\1=<redacted>"),
    # 전화번호
    (re.compile(r"\b\d{3}-\d{3,4}-\d{4}\b"), "<phone>"),
    # IPv4 (내부 IP 포함)
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
