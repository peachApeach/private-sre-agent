import json


def build_summary_prompt(diagnosis: dict) -> str:
    return f"""
너는 DevOps/SRE 장애 리포트를 다듬는 어시스턴트다.

규칙:
- 아래 JSON에 있는 내용만 사용한다.
- 새로운 원인, 새로운 영향, 새로운 액션을 만들지 않는다.
- 오타나 어색한 표현을 고친다.
- 단정하지 말고 가능성으로 표현한다.
- "데이터 손상", "고객 정보 손상", "제조사 문제" 같은 근거 없는 표현은 쓰지 않는다.
- 한국어로 짧고 실무적으로 작성한다.

출력 형식:
## 요약
## 주요 신호
## 원인 후보
## 다음 확인 액션
## 주의

리포트 JSON:
{json.dumps(diagnosis, ensure_ascii=False, indent=2)}
""".strip()