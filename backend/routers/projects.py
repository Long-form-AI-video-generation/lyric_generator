"""User project management router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.schemas import ProjectListResponse, ProjectResponse, ProjectUpdateRequest
from backend.models.user import User
from backend.services.project_service import (
    get_user_projects,
    get_project,
    utcnow,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_project_dict(project) -> dict:
    lyrics_data = None
    if project.lyrics:
        lyrics_data = {
            "raw_text": project.lyrics.raw_text,
            "timing_data": project.lyrics.timing_data,
            "source": project.lyrics.source,
        }

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

