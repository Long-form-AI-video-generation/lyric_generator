from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from backend.core.database import Base
from backend.models.user import User
from backend.models.project import Project
from backend.services.project_service import create_media_asset, create_project_export
from backend.services.s3_service import S3StorageService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="s3test@example.com",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session, test_user):
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="S3 Test Song",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_s3_unconfigured_behavior(tmp_path):
    s3 = S3StorageService()
    s3.bucket = ""
    s3.access_key = ""
    s3.secret_key = ""

    assert not s3.is_configured()

    dummy_file = tmp_path / "song.mp3"
    dummy_file.write_bytes(b"test audio content")

    assert not s3.upload_file(dummy_file, "some/key.mp3")
    assert not s3.download_file("some/key.mp3", tmp_path / "out.mp3")
    assert s3.generate_presigned_download_url("some/key.mp3") is None
    assert not s3.delete_file("some/key.mp3")


def test_s3_configured_calls_boto3(tmp_path):
    s3 = S3StorageService()
    s3.bucket = "my-r2-bucket"
    s3.access_key = "test-key"
    s3.secret_key = "test-secret"
    s3.endpoint_url = "https://my-account.r2.cloudflarestorage.com"

    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://my-account.r2.cloudflarestorage.com/presigned-url"
    s3._client = mock_client

    with patch.object(s3, "is_configured", return_value=True):
        assert s3.is_configured()

        dummy_file = tmp_path / "export.mp4"
        dummy_file.write_bytes(b"test video content")

        # Test upload
        uploaded = s3.upload_file(dummy_file, "exports/export.mp4", content_type="video/mp4")
        assert uploaded
        mock_client.upload_file.assert_called_once()

        # Test presigned URL
        url = s3.generate_presigned_download_url("exports/export.mp4", download_filename="video.mp4")
        assert url == "https://my-account.r2.cloudflarestorage.com/presigned-url"
        mock_client.generate_presigned_url.assert_called_once()

        # Test delete
        deleted = s3.delete_file("exports/export.mp4")
        assert deleted
        mock_client.delete_object.assert_called_once_with(Bucket="my-r2-bucket", Key="exports/export.mp4")


def test_create_media_asset_and_export_record(db_session, test_user, test_project):
    asset = create_media_asset(
        db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        asset_type="audio_source",
        s3_bucket="lyricvid-media",
        s3_key="users/1/projects/1/audio.mp3",
        file_name="audio.mp3",
        mime_type="audio/mpeg",
        file_size_bytes=1024,
    )
    assert asset.id is not None
    assert asset.s3_bucket == "lyricvid-media"
    assert asset.s3_key == "users/1/projects/1/audio.mp3"

    export_rec = create_project_export(
        db_session,
        project_id=test_project.id,
        user_id=test_user.id,
        media_asset_id=asset.id,
        resolution="1080p",
        format="mp4",
    )
    assert export_rec.id is not None
    assert export_rec.media_asset_id == asset.id
    assert export_rec.resolution == "1080p"
    assert export_rec.retention_expires_at is not None
