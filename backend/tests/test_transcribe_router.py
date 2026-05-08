from __future__ import annotations

import time

from backend.models.schemas import JobManifest, JobPhase, JobState
from backend.services.transcription_state import transcription_response_for_manifest


def _manifest(
    *,
    status: JobState = JobState.complete,
    phase: JobPhase | None = JobPhase.uploaded,
    lyrics_path: str | None = None,
) -> JobManifest:
    now = time.time()
    return JobManifest(
        job_token="token",
        original_filename="song.mp3",
        safe_filename="song.mp3",
        audio_path="/tmp/song.mp3",
        status=status,
        phase=phase,
        lyrics_path=lyrics_path,
        created_at=now,
        updated_at=now,
    )


def test_completed_transcription_is_not_requeued() -> None:
    response = transcription_response_for_manifest(
        _manifest(lyrics_path="/tmp/job/lyrics.json")
    )

    assert response is not None
    assert response.status == "complete"


def test_running_transcription_is_not_requeued() -> None:
    response = transcription_response_for_manifest(
        _manifest(status=JobState.processing, phase=JobPhase.transcribing)
    )

    assert response is not None
    assert response.status == "processing"


def test_failed_transcription_can_be_retried() -> None:
    response = transcription_response_for_manifest(
        _manifest(status=JobState.failed, phase=JobPhase.transcribing)
    )

    assert response is None
