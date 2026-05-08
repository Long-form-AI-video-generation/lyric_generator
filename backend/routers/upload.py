"""Audio upload endpoint."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.core.config import settings
from backend.core.errors import AppError
from backend.models.schemas import UploadResponse
from backend.services.media import probe_audio_duration, sanitize_filename, save_validated_upload
from backend.services.storage import storage

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(audio: UploadFile = File(...)) -> UploadResponse:
    token, job_dir = storage.reserve_job()
    safe_name = sanitize_filename(audio.filename, "song")
    try:
        audio_path, _ = await save_validated_upload(
            audio,
            job_dir / safe_name,
            max_bytes=settings.max_audio_bytes,
            kind="audio",
        )
        duration = probe_audio_duration(audio_path)
        manifest = storage.create_audio_job(
            token=token,
            original_filename=audio.filename or safe_name,
            audio_path=audio_path,
            duration_seconds=duration,
        )
        return UploadResponse(
            job_token=manifest.job_token,
            filename=manifest.safe_filename,
            duration_seconds=manifest.duration_seconds,
        )
    except AppError as exc:
        storage.delete_job(token)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        storage.delete_job(token)
        raise HTTPException(status_code=500, detail="The upload could not be processed.") from exc

