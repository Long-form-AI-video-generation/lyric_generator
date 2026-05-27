

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

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


@router.post("/art-direct", response_model=QueueResponse, summary="Run the AI art direction pass")
async def art_direct(
    request: ArtDirectRequest,
    background_tasks: BackgroundTasks,
) -> QueueResponse:
    
    try:
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
