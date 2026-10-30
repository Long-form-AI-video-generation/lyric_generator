import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_type = Column(String(50), nullable=False)  # 'audio_source', 'background_image', 'background_video', 'temp_render'
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    is_temporary = Column(Boolean, nullable=False, default=False)
    retention_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="media_assets")
    project = relationship("Project", back_populates="media_assets")
