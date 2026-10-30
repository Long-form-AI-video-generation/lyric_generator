"""Audio upload endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.errors import AppError
from backend.models.schemas import UploadResponse
from backend.models.user import User
from backend.services.media import probe_audio_duration, sanitize_filename, save_validated_upload
from backend.services.project_service import create_media_asset, create_project, create_video_job
from backend.services.s3_service import s3_storage
from backend.services.storage import storage

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
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

        project = create_project(db, current_user, title=audio.filename or safe_name)
        create_video_job(db, project.id, current_user, job_type="upload", credits_cost=0)

        if s3_storage.is_configured():
            s3_key = f"users/{current_user.id}/projects/{project.id}/audio/{safe_name}"
            uploaded = s3_storage.upload_file(
                audio_path,
                s3_key,
                content_type=audio.content_type or "audio/mpeg",
            )
            if uploaded:
                create_media_asset(
                    db,
                    user_id=current_user.id,
                    project_id=project.id,
                    asset_type="audio_source",
                    s3_bucket=s3_storage.bucket,
                    s3_key=s3_key,
                    file_name=safe_name,
                    mime_type=audio.content_type or "audio/mpeg",
                    file_size_bytes=audio_path.stat().st_size,
                )

        manifest = storage.create_audio_job(
            token=token,
            original_filename=audio.filename or safe_name,
            audio_path=audio_path,
            duration_seconds=duration,
            user_id=str(current_user.id),
            project_id=str(project.id),
        )
        return UploadResponse(
            job_token=manifest.job_token,
            filename=manifest.safe_filename,
            duration_seconds=manifest.duration_seconds,
            project_id=str(project.id),
        )
    except AppError as exc:
        storage.delete_job(token)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        storage.delete_job(token)
        raise HTTPException(status_code=500, detail="The upload could not be processed.") from exc
