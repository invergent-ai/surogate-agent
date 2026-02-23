"""
FastAPI application factory for surogate-agent.

Import ``app`` to use with uvicorn:
    uvicorn surogate_agent.api.app:app
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from surogate_agent.api.routers import chat, sessions, skills, workspace


def create_app() -> FastAPI:
    application = FastAPI(
        title="surogate-agent API",
        description=(
            "REST API for the surogate-agent — role-aware deep agent with "
            "meta-skill for conversational skill development."
        ),
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(chat.router)
    application.include_router(skills.router)
    application.include_router(sessions.router)
    application.include_router(workspace.router)

    @application.get("/", include_in_schema=False)
    def index():
        return JSONResponse({
            "name": "surogate-agent",
            "version": "0.1.0",
            "docs": "/docs",
            "endpoints": {
                "chat":      "POST /chat",
                "skills":    "GET/POST /skills  ·  GET/DELETE /skills/{name}  ·  POST /skills/{name}/validate",
                "sessions":  "GET /sessions  ·  GET/DELETE /sessions/{id}  ·  GET/POST/DELETE /sessions/{id}/files/{file}",
                "workspace": "GET /workspace  ·  GET/DELETE /workspace/{skill}  ·  GET/POST/DELETE /workspace/{skill}/files/{file}",
            },
        })

    return application


app = create_app()
