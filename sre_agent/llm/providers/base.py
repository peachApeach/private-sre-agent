from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def summarize(self, diagnosis: dict, model: str) -> str: ...

    @abstractmethod
    def analyze_logs(self, logs: str, context: str, model: str) -> str:
        """원본 로그를 직접 분석하여 초기 진단을 반환."""
        ...

    @abstractmethod
    def chat(self, messages: list[dict], model: str) -> str:
        """멀티턴 대화. messages는 [{"role": "user"|"assistant", "content": str}] 형식."""
        ...
