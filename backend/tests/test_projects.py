from __future__ import annotations

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# Allow SQLite to compile PostgreSQL JSONB as JSON during tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from backend.core.database import Base
from backend.models.user import User
from backend.services.project_service import (
    create_project,
    get_user_projects,
    get_project,
    save_project_lyrics,
    save_storyboard_scenes,
    create_video_job,
    update_video_job_status,
)


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
        email="test@example.com",
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_and_get_project(db_session, test_user):
    project = create_project(db_session, test_user, title="My Song")
    assert project.id is not None
    assert project.title == "My Song"
    assert project.user_id == test_user.id

    projects = get_user_projects(db_session, test_user)
    assert len(projects) == 1
    assert projects[0].id == project.id

    fetched = get_project(db_session, project.id, test_user)
    assert fetched.id == project.id


def test_save_lyrics_and_storyboard(db_session, test_user):
    project = create_project(db_session, test_user, title="Song 2")

    timing_sample = [{"id": 1, "text": "Hello world", "start": 0.0, "end": 2.5}]
    lyrics = save_project_lyrics(
        db_session,
        project.id,
        test_user.id,
        raw_text="Hello world",
        timing_data=timing_sample,
    )
    assert lyrics.raw_text == "Hello world"
    assert lyrics.project_id == project.id

    scenes_sample = [
        {"start_time_ms": 0, "end_time_ms": 2500, "prompt": "cyberpunk city", "transition_type": "cut"}
    ]
    scenes = save_storyboard_scenes(db_session, project.id, scenes_sample)
    assert len(scenes) == 1
    assert scenes[0].prompt == "cyberpunk city"


def test_create_video_job_and_update_status(db_session, test_user):
    project = create_project(db_session, test_user, title="Video Job Test")

    job = create_video_job(db_session, project.id, test_user, job_type="transcription", credits_cost=1)
    assert job.status == "queued"
    assert job.credits_cost == 1

    updated = update_video_job_status(db_session, job.id, "processing")
    assert updated is not None
    assert updated.status == "processing"
    assert updated.started_at is not None
