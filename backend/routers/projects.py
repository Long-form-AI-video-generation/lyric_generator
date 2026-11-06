"""User project management router."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.schemas import ProjectListResponse, ProjectResponse, ProjectUpdateRequest
from backend.models.user import User
from backend.services.project_service import (
    get_user_projects,
    get_project,
    utcnow,
)
from backend.services.s3_service import s3_storage
from backend.services.storage import storage

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_project_dict(project) -> dict:
    lyrics_data = None
    if project.lyrics:
        lyrics_data = {
            "raw_text": project.lyrics.raw_text,
            "timing_data": project.lyrics.timing_data,
            "source": project.lyrics.source,
        }

    latest_export = None
    if project.exports:
        exp = project.exports[-1]
        filename = exp.media_asset.file_name if exp.media_asset else "video.mp4"
        latest_export = {
            "id": str(exp.id),
            "resolution": exp.resolution,
            "format": exp.format,
            "file_name": filename,
            "download_url": f"/api/download/{project.id}",
            "created_at": exp.created_at.isoformat(),
        }

    audio_data = None
    for asset in (project.media_assets or []):
        if asset.asset_type == "audio_source":
            audio_data = {
                "id": str(asset.id),
                "file_name": asset.file_name,
                "mime_type": asset.mime_type,
                "file_size_bytes": asset.file_size_bytes,
                "url": f"/api/projects/{project.id}/audio",
            }
            break

    return {
        "id": str(project.id),
        "title": project.title,
        "status": project.status,
        "styling_config": project.styling_config or {},
        "lyrics": lyrics_data,
        "scenes": [
            {
                "scene_order": s.scene_order,
                "start_time_ms": s.start_time_ms,
                "end_time_ms": s.end_time_ms,
                "prompt": s.prompt,
                "transition_type": s.transition_type,
            }
            for s in (project.scenes or [])
        ],
        "latest_export": latest_export,
        "audio": audio_data,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.get("", response_model=ProjectListResponse)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectListResponse:
    projects = get_user_projects(db, current_user)
    return ProjectListResponse(projects=[_to_project_dict(p) for p in projects])


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_detail(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = get_project(db, project_id, current_user)
    return ProjectResponse.model_validate(_to_project_dict(project))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = get_project(db, project_id, current_user)

    if request.title is not None:
        project.title = request.title
    if request.styling_config is not None:
        project.styling_config = request.styling_config

    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(_to_project_dict(project))


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    project = get_project(db, project_id, current_user)
    project.deleted_at = utcnow()
    db.commit()
    return {"status": "deleted"}


@router.get("/{project_id}/audio")
def get_project_audio(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project(db, project_id, current_user)

    # 1. Check local storage if file exists
    for manifest_file in settings.temp_root.glob("*/manifest.json"):
        try:
            m = storage.read_manifest(manifest_file.parent.name)
            if m.project_id == str(project.id) and m.audio_path and Path(m.audio_path).exists():
                return FileResponse(path=m.audio_path, media_type="audio/mpeg", filename=m.safe_filename)
        except Exception:
            continue

    # 2. Check S3/R2 presigned URL
    for asset in (project.media_assets or []):
        if asset.asset_type == "audio_source" and s3_storage.is_configured():
            presigned_url = s3_storage.generate_presigned_download_url(
                asset.s3_key,
                expires_in=settings.download_ttl_seconds,
            )
            if presigned_url:
                return RedirectResponse(url=presigned_url, status_code=307)

    raise HTTPException(status_code=404, detail="Audio file not found for this project.")

