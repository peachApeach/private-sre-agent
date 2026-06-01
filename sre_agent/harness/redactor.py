# 민감정보 마스킹 
import re

REDACTION_RULES: list[tuple[str, str]] = [
    (r"[\w\.-]+@[\w\.-]+\.\w+", "<email>"),
    (r"Bearer\s+[A-Za-z0-9\._\-]+", "Bearer <token>"),
    (r"(?i)password=[^&\s]+", "password=<redacted>"),
    (r"(?i)token=[^&\s]+", "token=<redacted>"),
    (r"\b\d{3}-\d{3,4}-\d{4}\b", "<phone>"),
]

def redact(text: str) -> str:
    for pattern, replacement in REDACTION_RULES:
        text = re.sub(pattern, replacement, text)
    return text