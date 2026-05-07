"""Transcription job state helpers."""

from __future__ import annotations

from backend.models.schemas import JobManifest, JobPhase, JobState, QueueResponse


def transcription_response_for_manifest(manifest: JobManifest) -> QueueResponse | None:
    """Return a terminal/in-flight response when transcription should not requeue."""

    if manifest.lyrics_path:
        return QueueResponse(job_token=manifest.job_token, status="complete")
    if manifest.phase == JobPhase.transcribing and manifest.status in {
        JobState.queued,
        JobState.processing,
    }:
        return QueueResponse(job_token=manifest.job_token, status=manifest.status.value)
    return None

