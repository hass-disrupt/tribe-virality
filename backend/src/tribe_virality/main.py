"""FastAPI app factory and entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .jobs import get_queue
from .routes import attempts as attempts_routes
from .routes import health as health_routes
from .routes import jobs as jobs_routes
from .routes import upload as upload_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_dirs()
    init_db()
    get_queue().ensure_worker_started()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TRIBE Virality API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload_routes.router)
    app.include_router(jobs_routes.router)
    app.include_router(attempts_routes.router)
    app.include_router(health_routes.router)

    return app


app = create_app()
