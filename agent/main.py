"""FastAPI app factory. Route logic lives in `api/routers/`; this module
only wires them together."""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(".env")  # must run before any module that reads env vars at import time

from fastapi import FastAPI

from api.routers import agents, auth, chat, documents, estates, health, letters, notify
from observability.phoenix import init_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ProbatePilot Agent", lifespan=lifespan)
    for router in (health.router, auth.router, estates.router, documents.router, agents.router, chat.router, letters.router, notify.router):
        app.include_router(router)
    return app


app = create_app()
