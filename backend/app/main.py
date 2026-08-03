import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import _health_monitor, router
from app.core.guardian import Guardian


@asynccontextmanager
async def lifespan(app: FastAPI):
    Guardian().boot_check()
    app.state.health_task = asyncio.create_task(_health_monitor())
    yield
    app.state.health_task.cancel()


app = FastAPI(title="NOVA Cognitive Companion", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import os

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("NOVA_HOST", "127.0.0.1"),
        port=int(os.environ.get("NOVA_PORT", "8000")),
    )
