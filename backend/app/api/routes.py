import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.models import ChatMessage, ConfigPayload, HealthResponse
from app.core.kernel import Kernel

router = APIRouter()
kernel = Kernel()

CONFIG_FILE = Path(os.path.expanduser("~")) / ".nova_memory" / "config.json"
HEALTH_INTERVAL_SECONDS = 6 * 60 * 60

connections: set = set()


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"mode": "local", "backend_ip": ""}


def save_config(config: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), "utf-8")


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model=type(kernel.adapter).__name__,
        memory_entries=kernel.memory.count(),
    )


@router.get("/api/config", response_model=ConfigPayload)
async def get_config():
    return ConfigPayload(**load_config())


@router.post("/api/config", response_model=ConfigPayload)
async def set_config(config: ConfigPayload):
    save_config(config.model_dump())
    return config


async def _health_monitor():
    while True:
        await asyncio.sleep(HEALTH_INTERVAL_SECONDS)
        try:
            issues = await asyncio.to_thread(kernel.guardian.health_check)
            if issues:
                fixes = await asyncio.to_thread(kernel.guardian.auto_heal, issues)
                message = (
                    "Boss, maine apna thoda sa repair kar liya. Sab smooth hai."
                    if fixes
                    else "Boss, thodi dikkat dikhi, main ispe kaam kar rahi hoon."
                )
                for ws in list(connections):
                    try:
                        await ws.send_json({"type": "notice", "payload": message})
                    except Exception:
                        pass
        except Exception:
            pass


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    loop = asyncio.get_running_loop()

    def progress_cb(message: str):
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({"type": "progress", "payload": message}), loop
        )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                message = ChatMessage(**data)
            except (json.JSONDecodeError, ValueError):
                await websocket.send_json(
                    {"type": "error", "payload": "Invalid JSON message"}
                )
                continue
            if message.type == "voice_text":
                try:
                    result = await asyncio.to_thread(
                        kernel.process, message.payload, progress_cb=progress_cb
                    )
                    await websocket.send_json(
                        {
                            "type": "result",
                            "payload": result["text"],
                            "requires_confirmation": result.get(
                                "requires_confirmation", False
                            ),
                            "intent": result.get("intent"),
                        }
                    )
                except Exception:
                    await websocket.send_json(
                        {
                            "type": "result",
                            "payload": "Boss, main thoda restart hua. Ab sab theek hai.",
                            "requires_confirmation": False,
                            "intent": None,
                        }
                    )
            elif message.type == "ping":
                await websocket.send_json({"type": "pong", "payload": "pong"})
            else:
                await websocket.send_json(
                    {"type": "error", "payload": f"Unknown message type: {message.type}"}
                )
    except WebSocketDisconnect:
        connections.discard(websocket)
