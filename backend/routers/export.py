"""MP4 export and download endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from backend.core.config import settings
from backend.core.errors import AppError, ValidationAppError, WorkerUnavailableError
from backend.models.schemas import ExportSettings, JobPhase, JobState, QueueResponse, parse_lyrics_payload, validation_issues
from backend.services.job_runner import run_export_job
from backend.services.media import sanitize_filename, save_validated_upload
from backend.services.presets import preset_service
from backend.services.storage import storage

router = APIRouter(tags=["export"])


def _queue_export(job_token: str, background_tasks: BackgroundTasks) -> None:
    if settings.use_celery:
        try:
            from backend.tasks.celery_tasks import export_job

            export_job.delay(job_token)
            return
        except Exception as exc:
            raise WorkerUnavailableError("Could not queue export. Is Redis running?") from exc
    background_tasks.add_task(run_export_job, job_token)


@router.post("/export", response_model=QueueResponse)
async def export_video(
    background_tasks: BackgroundTasks,
    job_token: str = Form(...),
    lyrics: str = Form(...),
    preset_id: str | None = Form(default=None),
    resolution: str = Form(default="1080p"),
    fps: int = Form(default=30),
    background: UploadFile | None = File(default=None),
) -> QueueResponse:
    try:
        storage.read_manifest(job_token)
        try:
            lyrics_payload = json.loads(lyrics)
            lyrics_model = parse_lyrics_payload(lyrics_payload)
            settings_model = ExportSettings(resolution=resolution, fps=fps)
        except json.JSONDecodeError as exc:
            raise ValidationAppError("Lyrics must be valid JSON.") from exc
        except ValidationError as exc:
            issues = validation_issues(exc)
            raise ValidationAppError(issues.model_dump_json()) from exc

        if bool(background) == bool(preset_id):
            raise ValidationAppError("Choose either a background upload or a preset.")

        background_path = None
        if background is not None:
            safe_name = sanitize_filename(background.filename, "background")
            background_path, _ = await save_validated_upload(
                background,
                storage.job_dir(job_token) / "backgrounds" / safe_name,
                max_bytes=settings.max_background_bytes,
                kind="image",
            )
        elif preset_id:
            preset_service.resolve_full_path(preset_id)

        storage.write_json(
            job_token,
            "export_request.json",
            {
                "lyrics": lyrics_model.model_dump(mode="json"),
                "settings": settings_model.model_dump(mode="json"),
                "preset_id": preset_id,
                "background_path": str(background_path) if background_path else None,
            },
        )
        storage.update(
            job_token,
            status=JobState.queued,
            phase=JobPhase.rendering,
            progress_pct=0,
            error="",
            debug_log="",
            result_path="",
        )
        _queue_export(job_token, background_tasks)
        return QueueResponse(job_token=job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/download/{job_token}")
async def download(job_token: str) -> FileResponse:
    try:
        manifest = storage.read_manifest(job_token)
        if manifest.status != JobState.complete or not manifest.result_path:
            raise HTTPException(status_code=409, detail="The video is not ready yet.")
        result_path = Path(manifest.result_path)
        if not result_path.exists():
            raise HTTPException(status_code=404, detail="The rendered file has expired.")
        filename = result_path.name
        return FileResponse(
            result_path,
            media_type="video/mp4",
            filename=filename,
            background=BackgroundTask(storage.delete_job, job_token),
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
