from abc import ABC, abstractmethod
from typing import Iterator


class ModelAdapter(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream(self, prompt: str) -> Iterator[str]:
        raise NotImplementedError
