"""Database service layer for Project, LyricsTrack, StoryboardScene, MediaAsset, and VideoJob."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.core.errors import NotFoundError, ForbiddenError
from backend.models.project import Project, LyricsTrack, StoryboardScene
from backend.models.job import VideoJob, ProjectExport
from backend.models.media import MediaAsset
from backend.models.user import User


def utcnow():
    return datetime.now(timezone.utc)


def create_project(db: Session, user: User, title: str = "Untitled Project") -> Project:
    project = Project(
        user_id=user.id,
        title=title,
        status="draft",
        styling_config={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_user_projects(db: Session, user: User) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.user_id == user.id, Project.deleted_at.is_(None))
        .order_by(desc(Project.created_at))
        .all()
    )


def get_project(db: Session, project_id: str | uuid.UUID, user: User) -> Project:
    if isinstance(project_id, str):
        try:
            project_id = uuid.UUID(project_id)
        except ValueError:
            raise NotFoundError("Invalid project ID format.")

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise NotFoundError("Project not found.")
    if project.user_id != user.id and user.role != "admin":
        raise ForbiddenError("You do not have access to this project.")
    return project


def save_project_lyrics(
    db: Session,
    project_id: str | uuid.UUID,
    user_id: str | uuid.UUID | None,
    raw_text: str,
    timing_data: list[dict[str, Any]],
    source: str = "whisper",
) -> LyricsTrack:
    if isinstance(project_id, str):
        try:
            project_id = uuid.UUID(project_id)
        except ValueError:
            raise NotFoundError("Invalid project ID format.")

    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise NotFoundError("Project not found.")

    lyrics = db.query(LyricsTrack).filter(LyricsTrack.project_id == project.id).first()
    if not lyrics:
        lyrics = LyricsTrack(
            project_id=project.id,
            raw_text=raw_text,
            timing_data=timing_data,
            source=source,
        )
        db.add(lyrics)
    else:
        lyrics.raw_text = raw_text
        lyrics.timing_data = timing_data
        lyrics.source = source
        lyrics.updated_at = utcnow()

    db.commit()
    db.refresh(lyrics)
    return lyrics


def save_storyboard_scenes(
    db: Session,
    project_id: str | uuid.UUID,
    scenes_data: list[dict[str, Any]],
) -> list[StoryboardScene]:
    if isinstance(project_id, str):
        try:
            project_id = uuid.UUID(project_id)
        except ValueError:
            raise NotFoundError("Invalid project ID format.")

    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise NotFoundError("Project not found.")

    db.query(StoryboardScene).filter(StoryboardScene.project_id == project.id).delete()

    created_scenes = []
    for idx, sc in enumerate(scenes_data):
        scene = StoryboardScene(
            project_id=project.id,
            scene_order=idx,
            start_time_ms=int(sc.get("start_time_ms", 0)),
            end_time_ms=int(sc.get("end_time_ms", 0)),
            prompt=sc.get("prompt", ""),
            transition_type=sc.get("transition_type", "cut"),
        )
        db.add(scene)
        created_scenes.append(scene)

    db.commit()
    return created_scenes


def create_video_job(
    db: Session,
    project_id: str | uuid.UUID,
    user: User,
    job_type: str,
    credits_cost: int = 1,
) -> VideoJob:
    if isinstance(project_id, str):
        try:
            project_id = uuid.UUID(project_id)
        except ValueError:
            raise NotFoundError("Invalid project ID format.")

    job = VideoJob(
        project_id=project_id,
        user_id=user.id,
        job_type=job_type,
        status="queued",
        credits_cost=credits_cost,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_video_job_status(
    db: Session,
    job_id: str | uuid.UUID,
    status: str,
    error_message: str | None = None,
) -> VideoJob | None:
    if isinstance(job_id, str):
        try:
            job_id = uuid.UUID(job_id)
        except ValueError:
            return None

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        return None

    job.status = status
    if status == "processing" and not job.started_at:
        job.started_at = utcnow()
    elif status in ("completed", "failed", "cancelled"):
        job.completed_at = utcnow()

    if error_message:
        job.error_message = error_message

    db.commit()
    db.refresh(job)
    return job


def create_media_asset(
    db: Session,
    user_id: str | uuid.UUID,
    project_id: str | uuid.UUID | None,
    asset_type: str,
    s3_bucket: str,
    s3_key: str,
    file_name: str,
    mime_type: str = "application/octet-stream",
    file_size_bytes: int = 0,
    is_temporary: bool = False,
) -> MediaAsset:
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(project_id, str):
        project_id = uuid.UUID(project_id)

    asset = MediaAsset(
        user_id=user_id,
        project_id=project_id,
        asset_type=asset_type,
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        file_name=file_name,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        is_temporary=is_temporary,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_project_export(
    db: Session,
    project_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    media_asset_id: str | uuid.UUID,
    job_id: str | uuid.UUID | None = None,
    resolution: str = "1080p",
    format: str = "mp4",
    retention_days: int = 30,
) -> ProjectExport:
    if isinstance(project_id, str):
        project_id = uuid.UUID(project_id)
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(media_asset_id, str):
        media_asset_id = uuid.UUID(media_asset_id)
    if isinstance(job_id, str):
        job_id = uuid.UUID(job_id)

    retention_expires_at = utcnow() + timedelta(days=retention_days)

    export_rec = ProjectExport(
        project_id=project_id,
        user_id=user_id,
        job_id=job_id,
        media_asset_id=media_asset_id,
        resolution=resolution,
        format=format,
        retention_expires_at=retention_expires_at,
    )
    db.add(export_rec)

    # Mark parent project as completed
    proj = db.query(Project).filter(Project.id == project_id).first()
    if proj:
        proj.status = "completed"
        proj.updated_at = utcnow()

    db.commit()
    db.refresh(export_rec)
    return export_rec
