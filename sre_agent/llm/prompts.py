_MAX_LOG_CHARS = 12_000


def build_log_analysis_prompt(logs: str, rule_context: str) -> str:
    truncated = logs[-_MAX_LOG_CHARS:] if len(logs) > _MAX_LOG_CHARS else logs
    return f"""You are an SRE. Respond ONLY in Korean (한국어). Do not use English in your response.

아래 로그를 직접 분석해서 장애 상황을 진단해라.

규칙:
- 반드시 한국어로만 답해라. 영어 응답은 절대 금지.
- 로그에서 직접 근거를 찾아라. 추측은 근거와 함께 명시해라.
- 타임스탬프, 반복 패턴, 에러 순서에 주목해라.
- 단정하지 말고 가능성으로 표현해라.

출력 형식:
## 주요 발견
## 에러 순서 / 타임라인 (있는 경우)
## 원인 후보
## 즉시 확인할 것

---
[rule 기반 사전 분석 결과]
{rule_context}

---
[로그 원본]
{truncated}
""".strip()


