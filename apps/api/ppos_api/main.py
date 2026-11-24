"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ppos import __version__
from ppos.ai.provider import AIOutputError, AIUnavailableError
from ppos.bootstrap import Container, build_container
from ppos.infrastructure.config import Settings
from ppos.infrastructure.db import connect
from ppos.infrastructure.migrations import current_version
from ppos.shared.clock import Clock
from ppos.shared.errors import (
    ConflictError,
    DataBoundaryError,
    NotFoundError,
    PposError,
    ValidationError,
)
from ppos_api.routes import ai, book, career, documents, notes, planning, sprints, tasks
from ppos_api.routes import time as time_routes
from ppos_api.schemas import HealthOut

log = logging.getLogger("ppos.api")

_STATUS: dict[type[Exception], int] = {
    AIUnavailableError: 503,
    AIOutputError: 502,
    NotFoundError: 404,
    ValidationError: 422,
    ConflictError: 409,
    DataBoundaryError: 500,
}


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    container: Container = build_container(settings, clock)

    app = FastAPI(title="Personal Productivity & AI OS", version=__version__)
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(PposError)
    async def _ppos_error(_: Request, exc: PposError) -> JSONResponse:
        code = next((c for t, c in _STATUS.items() if isinstance(exc, t)), 400)
        return JSONResponse({"detail": str(exc), "error": type(exc).__name__}, status_code=code)

    @app.middleware("http")
    async def _timing(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
        if request.url.path.startswith("/api/"):
            # Structured log; never log request bodies (private content).
            log.info(
                "request", extra={"method": request.method, "path": request.url.path,
                                  "status": response.status_code, "ms": round(elapsed_ms, 1)},
            )  # fmt: skip
        return response

    @app.get("/api/health", response_model=HealthOut, tags=["system"])
    def health() -> HealthOut:
        conn = connect(settings.db_path)
        try:
            version = current_version(conn)
        finally:
            conn.close()
        return HealthOut(
            status="ok",
            version=__version__,
            schema_version=version,
            data_dir=str(settings.local_data_dir),
            demo=(settings.local_data_dir / "DEMO").exists(),
            ai={"enabled": False, "note": "local LLM integration arrives in Phase 5"},
        )

    app.include_router(tasks.router)
    app.include_router(notes.router)
    app.include_router(planning.router)
    app.include_router(sprints.router)
    app.include_router(book.router)
    app.include_router(documents.router)
    app.include_router(career.router)
    app.include_router(ai.router)
    app.include_router(time_routes.router)

    dist = settings.web_dist_dir
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app
