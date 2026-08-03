from typing import Iterator

from app.core.adapters.base import ModelAdapter


class MockAdapter(ModelAdapter):
    def __init__(self, label: str = None):
        self.label = label

    def _tag(self, prompt: str) -> str:
        if self.label:
            return f"[{self.label}] {prompt}"
        return f"[MOCK] {prompt}"

    def generate(self, prompt: str) -> str:
        return self._tag(prompt)

    def stream(self, prompt: str) -> Iterator[str]:
        for token in prompt.split(" "):
            yield token + " "
