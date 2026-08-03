from typing import Literal, Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    type: str
    payload: str = ""


class ConfigPayload(BaseModel):
    mode: Literal["local", "cloud"] = "local"
    backend_ip: Optional[str] = ""


class HealthResponse(BaseModel):
    status: str
    model: str
    memory_entries: int
