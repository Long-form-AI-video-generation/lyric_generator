import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Untitled Project")
    styling_config = Column(JSONB, nullable=False, default=dict)
    status = Column(String(50), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="projects")
    lyrics = relationship("LyricsTrack", back_populates="project", uselist=False, cascade="all, delete-orphan")
    scenes = relationship("StoryboardScene", back_populates="project", cascade="all, delete-orphan", order_by="StoryboardScene.scene_order")
    media_assets = relationship("MediaAsset", back_populates="project")
    video_jobs = relationship("VideoJob", back_populates="project", cascade="all, delete-orphan")
    exports = relationship("ProjectExport", back_populates="project", cascade="all, delete-orphan")


class LyricsTrack(Base):
    __tablename__ = "lyrics_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    raw_text = Column(Text, nullable=False, default="")
    timing_data = Column(JSONB, nullable=False, default=list)  # Array of words and timestamps
    source = Column(String(50), nullable=False, default="whisper")  # 'whisper', 'manual', 'synced'
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="lyrics")


class StoryboardScene(Base):
    __tablename__ = "storyboard_scenes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_order = Column(Integer, nullable=False)
    start_time_ms = Column(Integer, nullable=False)
    end_time_ms = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=True)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True)
    transition_type = Column(String(50), default="cut", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="scenes")
    media_asset = relationship("MediaAsset")
