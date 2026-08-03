from app.core.adapters.base import ModelAdapter
from app.core.adapters.mock_adapter import MockAdapter


class _OpenAIAdapter(ModelAdapter):
    def generate(self, prompt: str) -> str:
        raise NotImplementedError("OpenAI adapter not configured in V1")

    def stream(self, prompt: str) -> str:
        raise NotImplementedError("OpenAI adapter not configured in V1")


class _LocalAdapter(ModelAdapter):
    def generate(self, prompt: str) -> str:
        raise NotImplementedError("Local model adapter not configured in V1")

    def stream(self, prompt: str) -> str:
        raise NotImplementedError("Local model adapter not configured in V1")


def get_adapter(kind: str = "mock", **kwargs) -> ModelAdapter:
    kind = (kind or "mock").lower()
    if kind == "mock":
        return MockAdapter(label=kwargs.get("model_label"))
    if kind == "openai":
        return _OpenAIAdapter()
    if kind == "local":
        return _LocalAdapter()
    raise ValueError(f"Unknown adapter kind: {kind}")
