import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # 'transcription', 'alignment', 'preview_render', 'final_export'
    status = Column(String(50), nullable=False, default="queued")  # 'queued', 'processing', 'completed', 'failed', 'cancelled'
    celery_task_id = Column(String(255), nullable=True)
    credits_cost = Column(Integer, nullable=False, default=1)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="video_jobs")
    user = relationship("User", back_populates="video_jobs")


class ProjectExport(Base):
    __tablename__ = "project_exports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False)
    resolution = Column(String(20), nullable=False, default="1080p")
    format = Column(String(10), nullable=False, default="mp4")
    retention_expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="exports")
    user = relationship("User", back_populates="exports")
    media_asset = relationship("MediaAsset")
    job = relationship("VideoJob")
