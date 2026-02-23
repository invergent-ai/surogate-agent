"""
FastAPI application factory for surogate-agent.

Import ``app`` to use with uvicorn:
    uvicorn surogate_agent.api.app:app
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from surogate_agent.api.routers import chat, sessions, skills, workspace
from surogate_agent.api.routers import auth as auth_router

# Angular build output directory (set via env var; absent in dev)
_STATIC_DIR = os.environ.get("SUROGATE_STATIC_DIR", "")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup (idempotent)."""
    try:
        from surogate_agent.auth.database import create_tables
        create_tables()
    except Exception as exc:  # noqa: BLE001
        import warnings
        warnings.warn(f"Could not create auth tables: {exc}", stacklevel=2)
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="surogate-agent API",
        description=(
            "REST API for the surogate-agent — role-aware deep agent with "
            "meta-skill for conversational skill development."
        ),
        version="0.1.0",
        lifespan=_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # All API routes are mounted under /api so they coexist cleanly with the
    # Angular SPA catch-all at /.  The dev proxy (proxy.conf.json) forwards
    # /api/** to localhost:8000/api/** without stripping the prefix.
    application.include_router(auth_router.router, prefix="/api")
    application.include_router(chat.router,        prefix="/api")
    application.include_router(skills.router,      prefix="/api")
    application.include_router(sessions.router,    prefix="/api")
    application.include_router(workspace.router,   prefix="/api")

    # Serve Angular SPA at root when a build dir is present (skipped in dev).
    # A catch-all GET route is used instead of StaticFiles mount so that
    # client-side routes (e.g. /login, /developer) always fall back to
    # index.html rather than returning 404.  API routes registered above
    # take priority because Starlette matches routes in registration order.
    if _STATIC_DIR and os.path.isdir(_STATIC_DIR):
        _index = os.path.join(_STATIC_DIR, "index.html")

        @application.get("/{full_path:path}", include_in_schema=False)
        def spa_catch_all(full_path: str):
            candidate = os.path.join(_STATIC_DIR, full_path)
            if os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(_index)

    else:
        from fastapi.responses import JSONResponse

        @application.get("/", include_in_schema=False)
        def index():
            return JSONResponse({
                "name": "surogate-agent",
                "version": "0.1.0",
                "docs": "/docs",
                "ui": "not available (no static build present)",
                "endpoints": {
                    "auth":      "POST /api/auth/register  ·  POST /api/auth/login  ·  GET /api/auth/me",
                    "chat":      "POST /api/chat",
                    "skills":    "GET/POST /api/skills  ·  GET/DELETE /api/skills/{name}  ·  POST /api/skills/{name}/validate",
                    "sessions":  "GET /api/sessions  ·  GET/DELETE /api/sessions/{id}  ·  GET/POST/DELETE /api/sessions/{id}/files/{file}",
                    "workspace": "GET /api/workspace  ·  GET/DELETE /api/workspace/{skill}  ·  GET/POST/DELETE /api/workspace/{skill}/files/{file}",
                },
            })

    return application


app = create_app()
