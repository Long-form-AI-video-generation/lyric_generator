"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.core.errors import AppError
from backend.routers import export, presets, storyboard, transcribe, upload
from backend.services.cleanup import run_periodic_cleanup
from backend.services.presets import preset_service
from backend.services.storage import storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.ensure_root()
    preset_service.thumb_dir.mkdir(parents=True, exist_ok=True)
    cleanup_task = asyncio.create_task(
        run_periodic_cleanup(
            storage.cleanup_expired,
            interval_seconds=settings.cleanup_interval_seconds,
        )
    )
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        storage.cleanup_expired()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def upload_size_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and request.url.path.endswith("/upload"):
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if size > settings.max_audio_bytes + 1024 * 1024:
            return JSONResponse(
                {"detail": "Audio uploads are limited to 200 MB."},
                status_code=413,
            )
    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(upload.router, prefix=settings.api_prefix)
app.include_router(transcribe.router, prefix=settings.api_prefix)
app.include_router(storyboard.router, prefix=settings.api_prefix)
app.include_router(export.router, prefix=settings.api_prefix)
app.include_router(presets.router, prefix=settings.api_prefix)

app.mount(
    "/presets",
    StaticFiles(directory=str(preset_service.thumb_dir), check_dir=False),
    name="presets",
)
