from __future__ import annotations

from pathlib import Path

from backend.models.schemas import JobState
from backend.services.storage import JobStorage


def test_storage_creates_manifest_and_cleans_expired_job(tmp_path: Path) -> None:
    storage = JobStorage(root=tmp_path, ttl_seconds=-1)
    token, job_dir = storage.reserve_job()
    audio_path = job_dir / "song.mp3"
    audio_path.write_bytes(b"ID3")

    manifest = storage.create_audio_job(
        token=token,
        original_filename="song.mp3",
        audio_path=audio_path,
        duration_seconds=12.5,
    )
    assert manifest.job_token == token
    assert storage.read_manifest(token).status == JobState.complete

    assert storage.cleanup_expired() == 1
    assert not job_dir.exists()

