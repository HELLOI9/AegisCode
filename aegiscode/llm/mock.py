from aegiscode.llm.base import LLMClient


class MockExhaustedError(RuntimeError): ...


class MockLLM(LLMClient):
    def __init__(self, scripted_responses: list[str]):
        self._queue = list(scripted_responses)
        self.received_messages: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.received_messages.append(list(messages))
        if not self._queue:
            raise MockExhaustedError("no scripted responses left")
        return self._queue.pop(0)
