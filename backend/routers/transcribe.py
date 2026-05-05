"""Transcription, status, and lyrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.core.config import settings
from backend.core.errors import AppError, WorkerUnavailableError
from backend.models.schemas import AlignRequest, JobPhase, JobState, LyricsFile, QueueResponse, StatusResponse, TranscribeRequest
from backend.services.job_runner import run_alignment_job, run_transcription_job
from backend.services.storage import storage

router = APIRouter(tags=["jobs"])


def _queue_transcription(job_token: str, background_tasks: BackgroundTasks) -> None:
    if settings.use_celery:
        try:
            from backend.tasks.celery_tasks import transcribe_job

            transcribe_job.delay(job_token)
            return
        except Exception as exc:
            raise WorkerUnavailableError("Could not queue transcription. Is Redis running?") from exc
    background_tasks.add_task(run_transcription_job, job_token)


@router.post("/transcribe", response_model=QueueResponse)
async def transcribe(
    request: TranscribeRequest,
    background_tasks: BackgroundTasks,
) -> QueueResponse:
    try:
        storage.read_manifest(request.job_token)
        storage.update(
            request.job_token,
            status=JobState.queued,
            phase=JobPhase.transcribing,
            progress_pct=0,
            error="",
            debug_log="",
        )
        _queue_transcription(request.job_token, background_tasks)
        return QueueResponse(job_token=request.job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/align", response_model=QueueResponse)
async def align(
    request: AlignRequest,
    background_tasks: BackgroundTasks,
) -> QueueResponse:
    try:
        storage.read_manifest(request.job_token)
        storage.update(
            request.job_token,
            status=JobState.queued,
            phase=JobPhase.transcribing,
            progress_pct=0,
            error="",
            debug_log="",
        )
        if settings.use_celery:
            try:
                from backend.tasks.celery_tasks import align_job

                align_job.delay(request.job_token, request.lyrics_text)
            except Exception as exc:
                raise WorkerUnavailableError("Could not queue alignment. Is Redis running?") from exc
        else:
            background_tasks.add_task(run_alignment_job, request.job_token, request.lyrics_text)
        return QueueResponse(job_token=request.job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/status/{job_token}", response_model=StatusResponse)
async def status(job_token: str) -> StatusResponse:
    try:
        manifest = storage.read_manifest(job_token)
        result_url = None
        if manifest.status == JobState.complete and manifest.phase == JobPhase.rendering and manifest.result_path:
            result_url = f"{settings.api_prefix}/download/{job_token}"
        return StatusResponse(
            job_token=manifest.job_token,
            status=manifest.status,
            phase=manifest.phase,
            progress_pct=manifest.progress_pct,
            result_url=result_url,
            error=manifest.error or None,
            debug_log=None if settings.hide_internal_errors else (manifest.debug_log or None),
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/lyrics/{job_token}", response_model=LyricsFile)
async def lyrics(job_token: str) -> LyricsFile:
    try:
        manifest = storage.read_manifest(job_token)
        if not manifest.lyrics_path:
            raise HTTPException(status_code=409, detail="Lyrics are not ready yet.")
        return LyricsFile.model_validate(storage.read_json(job_token, "lyrics.json"))
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

