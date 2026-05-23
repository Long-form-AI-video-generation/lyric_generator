

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from backend.core.config import settings
from backend.core.errors import AppError, WorkerUnavailableError
from backend.models.schemas import ArtDirectRequest, JobPhase, JobState, QueueResponse
from backend.services.job_runner import run_art_direction_job
from backend.services.storage import storage

router = APIRouter(tags=["storyboard"])



def _queue_art_direction(
    job_token: str,
    style_prompt: str,
    background_tasks: BackgroundTasks,
) -> None:
    if settings.use_celery:
        try:
            from backend.tasks.celery_tasks import art_direction_job

            art_direction_job.delay(job_token, style_prompt)
            return
        except Exception as exc:
            raise WorkerUnavailableError(
                "Could not queue the art direction job. Is Redis running?"
            ) from exc
    background_tasks.add_task(run_art_direction_job, job_token, style_prompt)


def _validate_song_config_yaml(yaml_text: str | None) -> None:
    """Eagerly validate the YAML in the request so we can return a 422 synchronously."""
    if not yaml_text:
        return
    from backend.services.song_config import parse_song_config
    parse_song_config(yaml_text)  # raises ValueError on bad input


@router.post("/art-direct", response_model=QueueResponse, summary="Run the AI art direction pass")
async def art_direct(
    request: ArtDirectRequest,
    background_tasks: BackgroundTasks,
) -> QueueResponse:
    
    try:
        # Validate song config YAML early so we can return a 422 before queuing
        try:
            _validate_song_config_yaml(request.song_config_yaml)
        except ValueError as exc:
            raise AppError(str(exc), status_code=422) from exc

        manifest = storage.read_manifest(request.job_token)

        # Require that lyrics are already available
        if not manifest.lyrics_path:
            raise AppError(
                "No lyrics found for this job. "
                "Complete transcription or alignment before running art direction.",
                status_code=409,
            )

        # Persist the request so the worker can read it
        storage.write_json(
            request.job_token,
            "art_direction_request.json",
            {
                "style_prompt": request.style_prompt,
                "ai_image_generation": request.ai_image_generation,
                "background_image_b64": request.background_image_b64,
                "song_config_yaml": request.song_config_yaml,
            },
        )
        storage.update(
            request.job_token,
            status=JobState.queued,
            phase=JobPhase.art_directing,
            progress_pct=0,
            error="",
            debug_log="",
        )
        _queue_art_direction(request.job_token, request.style_prompt, background_tasks)
        return QueueResponse(job_token=request.job_token)

    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/storyboard/{job_token}", summary="Fetch the storyboard for a job")
async def get_storyboard(job_token: str) -> dict:
    try:
        return storage.read_json(job_token, "storyboard.json")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_token}/backgrounds", summary="List AI-generated background images for a job")
async def list_backgrounds(job_token: str) -> dict:
    """Return URLs for every bg_ai_NNN.jpg file written by the AI background pipeline."""
    try:
        job_dir = storage.job_dir(job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    backgrounds = []
    for f in sorted(job_dir.glob("bg_ai_*.jpg")):
        m = re.match(r"bg_ai_(\d+)\.jpg", f.name)
        if m:
            idx = int(m.group(1))
            backgrounds.append({"index": idx, "url": f"/api/jobs/{job_token}/bg/{idx}"})
    return {"backgrounds": backgrounds}


@router.get("/jobs/{job_token}/bg/{index}", summary="Serve an AI-generated background image")
async def serve_background(job_token: str, index: int):
    try:
        job_dir = storage.job_dir(job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    image_path = job_dir / f"bg_ai_{index:03d}.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Background image {index} not found.")
    return FileResponse(image_path, media_type="image/jpeg")
